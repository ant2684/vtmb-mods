"""Check the exact tracked tree before publication; never scan credentials."""
import re
import subprocess
import zipfile
from pathlib import Path
from infra.core import ROOT, require

FORBIDDEN={'.exe','.dll','.vtm','.bsp','.mdl','.sav','.log','.pdb','.wav','.pcm','.hl1','.hl2','.hl3'}


def inspect(root=ROOT, tracked=False):
    root=Path(root)
    if tracked:
        p=subprocess.run(['git','ls-files','--stage','-z'],cwd=root,capture_output=True,check=True)
        paths=[];blobs={}
        for entry in p.stdout.split(b'\0'):
            if not entry:continue
            metadata,name=entry.split(b'\t',1);mode,oid,stage=metadata.split()
            require(stage==b'0' and mode in [b'100644',b'100755'],'Unmerged, symlink or submodule in publication tree')
            path=root/name.decode('utf-8');paths.append(path)
            blobs[path]=subprocess.run(['git','cat-file','blob',oid.decode()],cwd=root,capture_output=True,check=True).stdout
    else:
        paths=[p for p in root.rglob('*') if p.is_file() and p.name!='local.json' and not any(x in {'.git','.local','__pycache__','build'} for x in p.relative_to(root).parts)]
    for path in paths:
        require(path.name.lower() not in {'local.json','settings.json','process.json','launch.json','observations.json','cleanup-ledger.json'} and not any(x.lower() in {'.local','build','__pycache__'} for x in path.relative_to(root).parts),'Private runtime/config file staged for publication')
        suffix=path.suffix.lower()
        require(suffix not in FORBIDDEN and suffix not in {'.zip','.7z','.rar','.tar','.gz'},'Nonpublic/game/compiled/archive file: '+str(path))
        raw=blobs[path] if tracked else path.read_bytes()
        require(b'MZ' != raw[:2], 'PE file disguised as source')
        if suffix in {'.py','.ps1','.c','.h','.cpp','.md','.json','.yml','.txt',''}:
            text=raw.decode('utf-8-sig')
            require(not re.search(r'[A-Z]:[/\\]Users[/\\][^/\\\s]+',text,re.I),'Personal Windows path/user in '+str(path))
            require(not re.search(r'gh[pousr]_[A-Za-z0-9]{30,}',text),'Credential-like string in public source')
    return {'files':len(paths),'tracked':tracked,'result':'PASS'}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--tracked',action='store_true');a=p.parse_args()
    print(inspect(tracked=a.tracked))
