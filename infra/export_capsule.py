"""Export a self-contained mod capsule without the original workspace.

Only source is exported by default. An optional exact reference VTM is a
local source fixture, never an installer or a compiled test helper.
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.core import ROOT, catalog, digest, read_json, require, sha
from infra.release import clean_pe, members


def export(mod,output,reference=None):
    require(mod in catalog()['mods'],'Unknown mod')
    output=Path(output)
    require(not output.exists(),'Refuse capsule overwrite')
    files={}
    for base in [ROOT/'mods'/mod,ROOT/'infra']:
        for path in base.rglob('*'):
            if not path.is_file() or any(x in ['build','__pycache__'] for x in path.relative_to(base).parts) or path.name=='README.md':continue
            require(path.suffix not in ['.exe','.pdb','.dll','.vtm','.zip','.pyc'],'Compiled/test debris')
            files[path.relative_to(ROOT).as_posix()]=path.read_bytes()
    for name in ['RunTests.ps1','Setup.ps1','requirements.txt','local.example.json','LICENSE','NOTICE']:
        files[name]=(ROOT/name).read_bytes()
    for path in (ROOT/'tests').glob('*.py'):files[path.relative_to(ROOT).as_posix()]=path.read_bytes()
    for name in ['gameplay.md','lessons.md']:
        files['docs/'+name]=(ROOT/'docs'/name).read_bytes()
    data=catalog();data['mods']={mod:data['mods'][mod]}
    files['infra/release_data.py']=('"""Frozen source verification inputs, not a distribution checksum manifest."""\nDATA = '+repr(data)+'\n').encode()
    if (ROOT/'docs/provenance.json').exists():
        provenance=read_json(ROOT/'docs/provenance.json')
    else:
        from infra.provenance_data import DATA
        import copy
        provenance=copy.deepcopy(DATA)
    provenance['files']=[r for r in provenance['files'] if r['file'].startswith('mods/'+mod+'/')]
    for record in provenance['files']:
        if record['published'] and record['file'] not in files:
            record['published']=False
            record['export_omission']='Original per-mod README retained in Git; isolated capsule has exactly one new top-level README'
    files['infra/provenance_data.py']=('"""Source origin records for isolated export verification."""\nDATA = '+repr(provenance)+'\n').encode()
    if reference:
        reference=Path(reference)
        clean_pe(reference.read_bytes(),data['mods'][mod]['exports'],mod)
        files['reference/'+data['mods'][mod]['filename']]=reference.read_bytes()
    maintenance = ('Console Pause Fix '+data['mods'][mod]['version']+' hides the Minimize button and disables its cached title-menu item using guarded native methods. For the included exact reference, use `./RunTests.ps1 -Suite offline -Mod console -Scenario console.exact -Candidate ./reference/console-pause-fix.vtm -Config ./local.json`. The embedded catalog is a dated verification input; this explicit selection avoids requiring older packages or a self-referential capsule hash. Use console.minimize with that reference for fresh gameplay observations. Recorded control coverage has an external five-second wait; an earlier menu-to-console opening failed despite engine key receipt, and its downstream cause remains unresolved. The plugin adds no wait. Sources retain cache-flush refusal probes; their known failure is not certified by passing ordinary checks.\n' if mod=='console' else 'Native code is unchanged from the current source capsule. Shared adapters and tests are maintenance updates, with no public mod version change.\n')
    files['README.md']=('# '+data['mods'][mod]['title']+' source capsule\n\nSelf-contained sources and regression infrastructure. This capsule is not installed into the game.\n\nUse `./RunTests.ps1 -Suite ci -Mod '+mod+' -Config ./local.json` or `-Suite offline`. Copy local.example.json to local.json and provide pinned Zig 0.15.2 and local inputs. See docs/gameplay.md for opt-in gameplay and recovery. Reference certificates are historical evidence only.\n\n'+maintenance).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,value in sorted(files.items()):
            entry=zipfile.ZipInfo(name,date_time=(2026,10,6,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,value)
    extracted=members(output)
    require(extracted==files,'Exported source bytes differ')
    require(sum(Path(n).name.lower() in ['readme.md','readme.txt'] for n in files)==1,'Exactly one README')
    require(not any('checksum' in Path(n).name.lower() or Path(n).name.lower() in ['sha256sums','manifest.sha256'] for n in files),'Checksum manifest forbidden')
    return {'mod':mod,'files':len(files),'sha256':digest(output),'source_only':reference is None}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mod',required=True);p.add_argument('--output',required=True);p.add_argument('--reference');a=p.parse_args()
    print(json.dumps(export(a.mod,a.output,a.reference),indent=2))
