"""Exact loaded-image tests; never rebuild or modify the candidate DLL."""
import argparse,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--plugin',type=Path,required=True);p.add_argument('--zig',required=True);p.add_argument('--game',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1];plugin=a.plugin.resolve();before=hashlib.sha256(plugin.read_bytes()).hexdigest().upper();checks=[]
def run(args):
 r=subprocess.run([str(x) for x in args],text=True,capture_output=True)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 checks.append(r.stdout.strip());return r.stdout.strip()
run([sys.executable,root/'tests/clean_pe.py',plugin,'--exports','loaded_vampire','--source',root/'plugin'])
with tempfile.TemporaryDirectory(prefix='vtmb-frenzy-verify-') as tmp:
 b=Path(tmp)
 for name in ('load_clean','exact_harness'):
  run([a.zig,'cc','-target','x86-windows-gnu','-O2','-g0','-Wall','-Wextra','-Werror',root/'tests'/(name+'.c'),'-o',b/(name+'.exe')])
 run([b/'load_clean.exe',plugin,'loaded_vampire'])
 run([b/'exact_harness.exe',plugin,a.game/'Vampire/dlls/vampire.dll',a.game/'Bin/engine.dll'])
 pass
assert hashlib.sha256(plugin.read_bytes()).hexdigest().upper()==before,'Candidate changed during verification'
result=dict(result='PASS',hash=before,bytes=plugin.stat().st_size,checks=checks)
if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
print('PASS exact final bytes',before)
