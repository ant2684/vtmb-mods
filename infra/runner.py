"""One command, finite tests, explicit missing-input and failure results."""
import argparse
import datetime
import os
import sys
import time
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.core import ROOT, Blocked, Failure, atomic_json, catalog, read_json, run


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--suite',choices=['ci','offline','gameplay','historical','faults'],default='offline')
    p.add_argument('--mod',default='all',choices=['all',*catalog()['mods']])
    p.add_argument('--config',type=Path)
    p.add_argument('--candidate',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--scenario')
    p.add_argument('--list',action='store_true')
    a=p.parse_args(argv)
    config=read_json(a.config) if a.config else {}
    if config.get('dependencies'):
        sys.path.insert(0,config['dependencies'])
    selected=list(catalog()['mods']) if a.mod=='all' else [a.mod]
    if a.candidate and a.mod=='all':
        p.error('--candidate requires a single --mod')
    definitions=[]
    if a.suite in ['ci','offline']:
        definitions.append(('infrastructure',120,'Portable synthetic regression tests; public tree, provenance and audit rejection'))
        definitions += [(m+'.build',600,'Pinned own-source build, clean PE, relocated Windows load, synthetic harness') for m in selected]
    if a.suite=='offline':
        definitions.append(('packages',120,'Frozen archive identity, exact membership, CRC, manuals, PE and BSP permission'))
        definitions += [(m+'.exact',900,'Final release/candidate machine code on local pinned native fixtures') for m in selected]
        if 'protean' in selected:definitions.append(('protean.models',180,'Different edition/sex MDL bytes, signed links, metadata, corruption and reconstruction'))
    if a.suite in ['gameplay','historical']:
        from infra.gameplay import SCENARIOS
        definitions += [(s['id'],s['timeout'],s['expected']) for s in SCENARIOS if s['mod'] in selected and (not a.scenario or a.scenario==s['id'])]
    if a.suite=='faults':
        definitions += [(m+'.cache_flush',180,'OS cache-flush refusal must refuse or roll back the exact native hook') for m in selected if m in ['console','protean','frenzy']]
    if a.candidate and a.suite in ['ci','historical','faults']:
        p.error('Candidate mode is supported by offline/gameplay only; never substitute a frozen release')
    if a.list:
        for name,timeout,expected in definitions:print(name, 'required', 'timeout='+str(timeout), expected)
        return 0
    if not definitions:
        p.error('No scenarios selected')
    session=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    report={'session':session,'suite':a.suite,'scenario_version':1,'python':sys.version,'platform':sys.platform,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Selected suite only; CI/offline never establish gameplay acceptance','results':[]}
    output=a.output or ROOT/'.local/results'/session/'report.json'
    for name,timeout,expected in definitions:
        start=time.monotonic();row={'id':name,'required':True,'expected':expected,'timeout_seconds':timeout}
        try:
            if name=='infrastructure':
                row['observed']=run([sys.executable,'-B','-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],timeout=timeout,cwd=ROOT)
            elif name.endswith('.build'):
                from infra.native import synthetic
                row['observed']=synthetic(name.split('.')[0],config)
            elif name=='packages':
                from infra.release import verify_archives
                row['observed']=verify_archives(config,a.mod)
            elif name.endswith('.exact'):
                from infra.native import exact
                row['observed']=exact(name.split('.')[0],config,a.candidate)
            elif name=='protean.models':
                from infra.release import models
                row['observed']=models(config)
            elif name.endswith('.cache_flush'):
                from infra.fault_probe import probe
                row['observed']=probe(name.split('.')[0],config)
                if row['observed']['status']=='BLOCKED':raise Blocked('OS fault probe not exercised: '+str(row['observed']))
                if row['observed']['status']=='FAIL':raise Failure(row['observed']['observed'])
            else:
                from infra.gameplay import execute
                row['observed']=execute(name,config,session,historical=a.suite=='historical',candidate=a.candidate)
            row['status']='PASS'
        except Blocked as e:
            row.update(status='BLOCKED',reason=str(e))
        except Exception as e:
            row.update(status='FAIL',reason=type(e).__name__+': '+str(e))
        row['duration_seconds']=round(time.monotonic()-start,3)
        report['results'].append(row)
        report['status']='PASS' if all(r['status']=='PASS' for r in report['results']) else 'FAIL' if any(r['status']=='FAIL' for r in report['results']) else 'BLOCKED'
        atomic_json(output,report)
        print(row['status'],name,row.get('reason',''),flush=True)
    atomic_json(output.with_suffix('.summary.json'),{k:v for k,v in report.items() if k!='results'} | {'counts':{s:sum(r['status']==s for r in report['results']) for s in ['PASS','FAIL','BLOCKED','SKIPPED']}})
    print('Overall',report['status'],'report:',output)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
