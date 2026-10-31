"""Owned-process file/settings transaction. No UI automation or input APIs."""
import hashlib,json,shutil,subprocess,winreg
from pathlib import Path
PINS={}
def require(value,message):
    if not value:raise RuntimeError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):Path(path).write_text(json.dumps(value,indent=2),encoding='utf8')
VIDEO_KEYS = (r'Software\Troika\Vampire\Settings', r'Software\Troika\Vampire\ResPatch')
VIDEO_NAMES = ('ScreenWidth', 'ScreenHeight', 'ScreenWindowed', 'ScreenBPP')


def running_games():
    result = subprocess.run(['powershell', '-NoProfile', '-Command',
        '@(Get-Process Vampire -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) | ConvertTo-Json -Compress'],
        capture_output=True, text=True, check=True)
    return json.loads(result.stdout.strip() or '[]')


def video_snapshot():
    result = {}
    for name in VIDEO_KEYS:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, name)
        except FileNotFoundError:
            result[name] = None
            continue
        values = {}
        with key:
            index = 0
            while True:
                try:
                    entry, value, kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                if entry in VIDEO_NAMES or name.endswith('ResPatch'):
                    values[entry] = [value, kind]
                index += 1
        result[name] = values
    require(result[VIDEO_KEYS[0]] is not None, 'Real-user video settings unavailable')
    return result


def restore_video(before):
    after = video_snapshot()
    if after == before:
        return
    for name, original in before.items():
        current = after[name]
        if original is None:
            if current is not None:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, name, 0, winreg.KEY_ALL_ACCESS) as key:
                    for entry in current:
                        winreg.DeleteValue(key, entry)
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, name)
        else:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, name) as key:
                for entry in set(current or {}) - set(original):
                    winreg.DeleteValue(key, entry)
                for entry, (value, kind) in original.items():
                    winreg.SetValueEx(key, entry, 0, kind, value)
    require(video_snapshot() == before, 'Video settings restoration failed')


def shortcut_snapshot():
    command = r'''$shell=New-Object -ComObject WScript.Shell; $rows=@(); foreach($dir in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'))){if(Test-Path -LiteralPath $dir){foreach($file in Get-ChildItem -LiteralPath $dir -Filter '*.lnk' -File){$link=$shell.CreateShortcut($file.FullName);if($link.TargetPath -match 'Vampire|Bloodlines|Loader'){$rows += [pscustomobject]@{Path=$file.FullName;Target=$link.TargetPath;Arguments=$link.Arguments;WorkingDirectory=$link.WorkingDirectory;Hash=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash}}}}}; ConvertTo-Json -InputObject $rows -Compress'''
    raw = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                         capture_output=True, check=True).stdout
    return raw.decode('cp866', 'replace')


class Transaction:
    """Retain originals and archive generated files before restoring, without tree deletion."""
    def __init__(self, game, session):
        self.game, self.session = game, session

    def inside_game(self, path):
        resolved = path.resolve()
        require(resolved.is_relative_to(self.game), 'Path escapes game directory: ' + str(path))
        return resolved

    def begin(self):
        require(not running_games(), 'User game running; refusing to launch or stop it')
        self.video = video_snapshot()
        dump(self.session / 'video-before.json', self.video)
        (self.session / 'shortcuts-before.txt').write_text(shortcut_snapshot(), encoding='utf8')
        self.trees = ['Unofficial_Patch/SAVE', 'Unofficial_Patch/cfg', 'Vampire/cfg',
                      'Unofficial_Patch/python', 'Unofficial_Patch/maps/graphs']
        self.records, self.directories = {}, {}
        paths = []
        for tree in self.trees:
            directory = self.inside_game(self.game / tree)
            self.directories[tree] = [str(p.relative_to(self.game)) for p in directory.rglob('*') if p.is_dir()]
            paths.extend(p for p in directory.rglob('*') if p.is_file())
        self.single = ['console.log', 'Vampire/console.log', 'Unofficial_Patch/console.log',
                       'logs/console.log', 'Vampire/logs/console.log', 'Unofficial_Patch/logs/console.log']
        paths.extend(self.game / name for name in self.single if (self.game / name).is_file())
        for path in paths:
            self.inside_game(path)
            relative = str(path.relative_to(self.game))
            target = self.session / 'backup' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            stat = path.stat()
            digest = sha(path)
            require(sha(target) == digest, 'Backup mismatch: ' + relative)
            self.records[relative] = {'sha256': digest, 'mtime_ns': stat.st_mtime_ns}
        dump(self.session / 'transaction.json', dict(game=str(self.game), trees=self.trees,
             single=self.single, files=self.records, directories=self.directories))

    def restore(self):
        require(not running_games(), 'A game is still running; restoration deferred; backups retained')
        generated = []
        paths = set()
        for tree in self.trees:
            paths.update(p for p in (self.game / tree).rglob('*') if p.is_file())
        paths.update(self.game / name for name in self.single if (self.game / name).is_file())
        # Windows preserves spelling but treats SAVE/save as the same directory.
        # Compare manifest keys case-insensitively before considering a file new.
        records_ci = {name.casefold(): record for name, record in self.records.items()}
        require(len(records_ci) == len(self.records), 'Ambiguous case-insensitive manifest')
        for path in paths:
            self.inside_game(path)
            relative = str(path.relative_to(self.game))
            original = records_ci.get(relative.casefold())
            if original is None or sha(path) != original['sha256']:
                archive = self.session / 'generated' / relative
                archive.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, archive)
                require(sha(path) == sha(archive), 'Generated file archive failed')
                generated.append(relative)
                if original is None:
                    path.unlink()
        for relative, record in self.records.items():
            destination = self.inside_game(self.game / relative)
            if not destination.exists() or sha(destination) != record['sha256'] or destination.stat().st_mtime_ns != record['mtime_ns']:
                source = self.session / 'backup' / relative
                require(sha(source) == record['sha256'], 'Original backup changed')
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            require(sha(destination) == record['sha256'] and destination.stat().st_mtime_ns == record['mtime_ns'],
                    'Restore verification failed: ' + relative)
        restore_video(self.video)
        require(json.loads(shortcut_snapshot()) == json.loads((self.session / 'shortcuts-before.txt').read_text(encoding='utf8')),
                'Shortcut changed during test')
        for relative, digest in PINS.items():
            require(sha(self.game / relative) == digest, 'Gameplay resource changed: ' + relative)
        dump(self.session / 'restored.json', {'restored': True, 'original_file_count': len(self.records),
             'video_unchanged': True, 'gameplay_hashes_unchanged': True,
             'generated_files_archived': generated})
