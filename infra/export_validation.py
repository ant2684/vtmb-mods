"""Exercise exported source dependencies from independent extractions."""
import argparse
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from infra.core import ROOT, atomic_json, catalog, read_json, require, run
from infra.export_capsule import export


def validate(config,output):
    rows=[]
    for mod in catalog()['mods']:
        with tempfile.TemporaryDirectory(prefix='vtmb-capsule-') as td:
            folder=Path(td);archive=folder/'source.zip'
            identity=export(mod,archive)
            extracted=folder/'checkout'
            with zipfile.ZipFile(archive) as z:z.extractall(extracted)
            require(sum(p.name.lower() in ['readme.md','readme.txt'] for p in extracted.rglob('*'))==1,'One source README')
            configuration=folder/'local.json';atomic_json(configuration,config)
            result=folder/'report.json'
            # Every subprocess imports from the extraction, never parent sources.
            try:
                log=run([sys.executable,'-B',extracted/'infra/runner.py','--suite','ci','--mod',mod,'--config',configuration,'--output',result],cwd=extracted,timeout=900,env={'PYTHONPATH':config.get('dependencies','')})
            except Exception as error:
                rows.append({**identity,'status':'FAIL','reason':str(error),'checks':read_json(result)['results'] if result.exists() else []})
                atomic_json(output,{'status':'FAIL','scope':'Isolated source capsule validation; original failure retained','results':rows})
                raise
            receipt=read_json(result);require(receipt['status']=='PASS','Isolated capsule tests failed')
            rows.append({**identity,'status':'PASS','checks':receipt['results'],'output':log})
            atomic_json(output,{'status':'PASS','scope':'Each mod exported and tested from its independent extraction; no old source-work directories','results':rows})
            print('PASS isolated source capsule',mod,flush=True)
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    validate(read_json(args.config),Path(args.output))
