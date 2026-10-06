"""Write-ahead file transaction with explicit crash recovery and preservation."""
import os
import shutil
import sys
import uuid
from pathlib import Path
from infra.core import Blocked, Failure, atomic_json, digest, read_json, require


class Transaction:
    def __init__(self, game_root, state_root):
        self.mutex = None
        self.game = Path(game_root).resolve()
        self.state = Path(state_root).resolve()
        require(self.game.is_dir(), 'Game/fixture root absent')
        require(self.state != self.game and self.game not in self.state.parents and self.state not in self.game.parents, 'State must be separate from game root')
        self.state.mkdir(parents=True, exist_ok=True)
        self.lock = self.state/'installation.lock'
        self.journal = self.state/'journal.json'
        self.installation_file = self.game/'.vtmb-regression.lock'
        self.data = read_json(self.journal) if self.journal.exists() else None

    def acquire_installation(self):
        # An installation-wide Windows mutex prevents different state_root
        # configurations from mutating the same game simultaneously.
        if os.name!='nt' or self.mutex is not None:return
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[wintypes.LPVOID,wintypes.BOOL,wintypes.LPCWSTR]
        kernel.CreateMutexW.restype=wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        kernel.ReleaseMutex.argtypes=[wintypes.HANDLE]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        from infra.core import sha
        name='Local\\VTMBRegression_'+sha(os.path.normcase(str(self.game)).encode())
        handle=kernel.CreateMutexW(None,False,name)
        require(bool(handle),'Installation mutex creation failed')
        wait=kernel.WaitForSingleObject(handle,0)
        if wait not in [0,128]:
            kernel.CloseHandle(handle)
            raise Blocked('This game installation is owned by another test controller')
        self.mutex=(kernel,handle)

    def release_installation(self):
        if getattr(self,'mutex',None):
            kernel,handle=self.mutex
            kernel.ReleaseMutex(handle);kernel.CloseHandle(handle);self.mutex=None

    def __del__(self):
        self.release_installation()

    def path(self, relative):
        require(isinstance(relative,str) and ':' not in relative and not relative.startswith(('/','\\')), 'Unsafe relative path')
        p=(self.game/relative).resolve()
        require(self.game in p.parents and not any(x=='..' for x in Path(relative).parts), 'Path escapes game root')
        # Resolve symlinks/junctions before any read, write or deletion.
        return p

    def start(self):
        if self.data and self.data['state'] != 'RESTORED':
            raise Blocked('Unfinished transaction; run infra/recover.py before another session: '+str(self.state))
        self.acquire_installation()
        try:
            fd=os.open(self.lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError as e:
            raise Blocked('Installation lock exists; explicit recovery required') from e
        with os.fdopen(fd,'w') as f:
            f.write(str(os.getpid()));f.flush();os.fsync(f.fileno())
        label=uuid.uuid4().hex
        self.data={'id':label,'state':'PREPARING','game_root':str(self.game),'operations':[],'owned_process':None,'launch_intent':None}
        (self.state/label/'originals').mkdir(parents=True)
        atomic_json(self.journal,self.data)
        try:
            fd=os.open(self.installation_file,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError as e:
            raise Blocked('Installation has a persistent unfinished-session lock: '+str(self.installation_file)) from e
        import json
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump({'id':label,'state_root':str(self.state),'journal':str(self.journal)},f);f.flush();os.fsync(f.fileno())
        self.data['installation_lock']=True;self.save()
        return self.state/label

    def watch_inventory(self):
        self.data['inventory']=[p.relative_to(self.game).as_posix() for p in self.game.rglob('*') if p.is_file()]
        self.save()

    def save(self):
        atomic_json(self.journal,self.data)

    def preserve(self, relative):
        require(self.data and self.data['state']!='RESTORED','No active transaction')
        old=next((r for r in self.data['operations'] if r['path']==relative),None)
        if old:return old
        target=self.path(relative)
        row={'path':relative,'exists':target.exists(),'before':None,'after':None,'kind':'preserved','restored':False}
        if target.exists():
            require(target.is_file(),'Only files are preserved')
            stat=target.stat();row.update(before=digest(target),mtime_ns=stat.st_mtime_ns,atime_ns=stat.st_atime_ns)
            backup=self.state/self.data['id']/'originals'/relative
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,backup)
            require(digest(backup)==row['before'],'Backup mismatch')
        self.data['operations'].append(row)
        self.save()
        return row

    def write(self, relative, data, crash=None):
        row=self.preserve(relative)
        require(row['kind']=='preserved','Refuse second write to same path without explicit transaction operation')
        row.update(after=__import__('hashlib').sha256(data).hexdigest().upper(),kind='write_intent')
        self.save()  # Durable intent includes expected bytes BEFORE replacement.
        if crash:crash('intent')
        target=self.path(relative);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        if crash:crash('write')
        require(digest(target)==row['after'],'Write verification mismatch')
        row['kind']='written';self.save()

    def allow_runtime(self, relative):
        row=self.preserve(relative)
        row['kind']='runtime_intent';self.save()

    def launch_intent(self, executable, arguments):
        self.data['launch_intent']={'executable':str(Path(executable).resolve()),'arguments':list(arguments),'state':'INTENT'}
        self.data['state']='LAUNCHING';self.save()

    def owned_process(self, pid, ticks):
        require(self.data['launch_intent'] is not None,'Launch intent missing')
        self.data['owned_process']={'Id':int(pid),'Ticks':int(ticks)}
        self.data['launch_intent']['state']='RECORDED';self.data['state']='RUNNING';self.save()

    def seal_runtime(self):
        """Called only by the live controller after stopping its PID and
        observing no game. Recovery must not infer this snapshot retroactively.
        """
        frozen={}
        for row in self.data['operations']:
            if row['kind']!='runtime_intent':continue
            target=self.path(row['path'])
            frozen[row['path']]={'sha256':digest(target) if target.exists() else None,
                                 'mtime_ns':target.stat().st_mtime_ns if target.exists() else None}
        self.data['runtime_after_stop']=frozen;self.save()

    def restore(self, process_stopped=False, runtime_safe=False, finalize=True):
        require(self.data is not None,'Journal missing; lock alone needs manual inspection')
        require(self.data['game_root']==str(self.game),'Journal belongs to different installation')
        if self.data['state']=='RESTORED':
            self.finish()
            return {'state':'RESTORED','idempotent':True}
        self.acquire_installation()
        if self.installation_file.exists():
            lock=read_json(self.installation_file)
            require(lock.get('id')==self.data['id'] and lock.get('state_root')==str(self.state),'Installation lock belongs to another session; use its recorded journal')
        if self.data['launch_intent'] and not self.data['owned_process']:
            raise Blocked('Launch intent exists without verified PID. Inspect the exact executable/start window; do not terminate an assumed process. Register a verified process or confirm no matching process before recovery.')
        if self.data['owned_process'] and not process_stopped:
            raise Blocked('Stop and verify only the recorded PID/start-time pair before restoring')
        if 'inventory' in self.data:
            registered={r['path'] for r in self.data['operations']}
            current={p.relative_to(self.game).as_posix() for p in self.game.rglob('*') if p.is_file()}
            unknown=current-set(self.data['inventory'])-registered
            if unknown:raise Blocked('Unregistered new files kept intact; reconcile before recovery: '+', '.join(sorted(unknown)))
        archive=self.state/self.data['id']/'after-tests'
        for row in reversed(self.data['operations']):
            target=self.path(row['path'])
            backup=self.state/self.data['id']/'originals'/row['path']
            if row['exists']:
                require(backup.is_file() and digest(backup)==row['before'],'Backup damaged; preserved current file: '+row['path'])
            current=digest(target) if target.exists() else None
            known=current in [row['before'],row['after']]
            if row['kind']=='runtime_intent':
                stamp=target.stat().st_mtime_ns if target.exists() else None
                original={'sha256':row['before'],'mtime_ns':row.get('mtime_ns')}
                observed={'sha256':current,'mtime_ns':stamp}
                frozen=self.data.get('runtime_after_stop',{}).get(row['path'])
                known=observed==original or observed==frozen
            if not known:
                raise Blocked('Unknown changed file; kept intact: '+row['path'])
            if current!=row['before'] and target.exists():
                evidence=archive/row['path'];evidence.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(target,evidence)
                require(digest(evidence)==current,'Evidence archive mismatch')
            if row['exists']:
                if current!=row['before']:shutil.copy2(backup,target)
                os.utime(target,ns=(row['atime_ns'],row['mtime_ns']))
                require(digest(target)==row['before'] and target.stat().st_mtime_ns==row['mtime_ns'],'Restoration mismatch')
            elif target.exists():
                target.unlink()  # Only a journaled task/runtime file, after evidence verification.
            row['restored']=True;self.save()
        self.data['state']='FILES_RESTORED';self.save()
        if finalize:self.finish()
        return {'state':'RESTORED','operations':len(self.data['operations'])}

    def finish(self):
        require(self.data['state'] in ['FILES_RESTORED','RESTORED'],'File restoration must finish before releasing installation lock')
        self.data['state']='RESTORED';self.save()
        if self.installation_file.exists():
            require(read_json(self.installation_file).get('id')==self.data['id'],'Never remove another session installation lock')
            self.installation_file.unlink()
        if self.lock.exists():self.lock.unlink()
        self.release_installation()
