"""Rerun dated auditors on private copies; never establish fresh acceptance."""
import shutil
import sys
import uuid
from pathlib import Path
from infra.core import ROOT,Blocked,atomic_json,catalog,digest,need,read_json,require,run
from infra.release import members

AUDITORS={
    'console':('mods/console/tests/gameplay/audit_console.py','gameplay-verification.json'),
    'protean':('mods/protean/tests/gameplay/audit_protean.py','protean-gameplay-verification.json'),
    'frenzy':('mods/frenzy/tests/gameplay/audit_frenzy.py','frenzy-gameplay-verification.json'),
    'subtitle':('mods/subtitle/tests/audit_evidence.py','audit.json'),
    'background':('mods/background/tests/audit_evidence.py','audit.json'),
    'history':('mods/history/tests/audit_scenarios.py','audit.json'),
}


def execute(mod,config):
    record=config.get('historical',{}).get(mod,{})
    source=Path(need(record,'evidence')).resolve()
    if not source.is_dir():raise Blocked('Historical evidence directory absent for '+mod)
    if mod=='subtitle' and not Path(need(record,'assets')).is_dir():raise Blocked('Historical local audio assets absent')
    if mod=='background' and not Path(need(record,'game_snapshot')).is_dir():raise Blocked('Historical game snapshot required; current restored installation cannot replace that snapshot')
    folder=ROOT/'.local/historical'/uuid.uuid4().hex;folder.mkdir(parents=True)
    identity={}
    for file in source.rglob('*'):
        require(not file.is_symlink() and (source in file.resolve().parents or file.resolve()==source),'Historical evidence contains redirected paths')
        if file.is_file():identity[file.relative_to(source).as_posix()]=digest(file)
    atomic_json(folder/'input-identity.json',identity)
    # Auditors may write derived reports. Originals and first failures remain
    # untouched, even when the legacy auditor expects a dated failed run.
    copied=folder/'evidence';shutil.copytree(source,copied)
    data=catalog()['mods'][mod];archive=Path(need(config,'releases'))/data['archive']
    if not archive.is_file():raise Blocked('Historical reference archive absent: '+data['archive'])
    require(digest(archive)==catalog()['archives'][data['archive']]['sha256'],'Wrong historical reference archive')
    binary=folder/data['filename'];binary.write_bytes(members(archive)['Bin/loader/'+data['filename']])
    script,receipt=AUDITORS[mod];output=copied/receipt
    if output.exists():output.unlink()  # Only our just-created disposable copy.
    args=[sys.executable,'-B',ROOT/script]
    if mod in ['console','protean','frenzy']:args += [copied,binary]
    elif mod=='history':args += [copied,binary,output]
    elif mod=='subtitle':args += ['--session',copied,'--assets',record['assets'],'--plugin',binary,'--output',output]
    else:args += ['--game',record['game_snapshot'],'--work',copied,'--output',output]
    log=run(args,timeout=900,env={'PYTHONPATH':config.get('dependencies','')},process_tree=True)
    (folder/'auditor-output.txt').write_text(log,encoding='utf-8')
    if not output.exists():raise Blocked('Dated auditor did not produce a complete certificate; partial/PENDING result is not PASS')
    result=read_json(output)
    require(result.get('result')=='PASS' or result.get('passed') is True,'Dated auditor did not confirm PASS')
    require(all(digest(source/name)==value for name,value in identity.items()),'Original historical evidence changed')
    receipt={'status':'PASS','scope':'Dated evidence only; no new game run, no new gameplay acceptance','artifact_sha256':digest(binary),'evidence':identity,'audit':result,'session_directory':str(folder)}
    atomic_json(folder/'result.json',receipt)
    return receipt
