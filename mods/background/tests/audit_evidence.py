"""Read-only audit of retained captures, exact payload and original-file inventory."""
import argparse, hashlib, json, struct
from pathlib import Path

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--game',required=True)
    ap.add_argument('--work',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args();g=Path(a.game);w=Path(a.work)
    rows=json.loads((w/'originals/files.json').read_text(encoding='utf-8-sig'))
    before={r['Path'].lower():r for r in rows};now=set()
    dirs=['Unofficial_Patch/cfg','Vampire/cfg','Unofficial_Patch/save','Vampire/save','Bin/loader','Unofficial_Patch/resource','Unofficial_Patch/python']
    for d in dirs:
        p=g/d
        if p.exists():
            for f in (p.rglob('*') if d.endswith('/python') else p.iterdir()):
                if f.is_file():now.add(str(f.relative_to(g)).lower())
    extra=sorted(now-set(before))
    assert extra==['bin\\loader\\cutscene-subtitle-background-fix.vtm'],extra
    for r in rows:assert sha(g/r['Path'])==r['Hash'],r['Path']
    for d in ['', 'Unofficial_Patch','Vampire']:
        for f in (g/d).iterdir():
            if f.is_file() and f.suffix.lower() in ['.log','.cfg','.txt','.exe','.inf']:
                assert str(f.relative_to(g)).lower() in before,str(f)
    expected=sha(w/'source/build/cutscene-subtitle-background-fix.vtm')
    assert all(sha(p)==expected for p in [g/extra[0],w/'payload/Bin/loader/cutscene-subtitle-background-fix.vtm'])
    def observed(label):
        return [json.loads(l) for l in (w/'sessions'/label/'observations.jsonl').read_text().splitlines()]
    baseline=observed('direct_a/baseline');candidate=observed('candidate_a/comparison');final=observed('final_a/final')
    dimensions=[]
    for index in [10,14]:
        states=[struct.unpack_from('<4I',bytes.fromhex(r[index]['chat_raw']),0x90) for r in [baseline,candidate,final]]
        assert states[0]==states[1]==states[2],states
        dimensions.append({'frame':index,'y':states[0][0],'width':states[0][2],'height':states[0][3]})
    for label in ['candidate_a/comparison','candidate_a/camarilla','final_a/final']:
        data=observed(label)
        assert all(r['background_branch']=='e9bf00000090' for r in data)
        assert any(r['cinematic_fade']>0 for r in data)
    for label in ['candidate_a/radio','candidate_a/tv']:
        assert all(r['cinematic_fade']==0 for r in observed(label))
    launch=json.loads((w/'sessions/final_a/launch.json').read_text(encoding='utf-8-sig'))
    assert launch['PluginHash']==expected
    report={'passed':True,'original_file_count':len(rows),'only_inventory_addition':extra,
            'plugin_sha256':expected,'dll_files_unchanged':True,'source_payload_game_equal':True,
            'single_and_multi_caption_bounds':dimensions,
            'limit':'Capture/layout and native-code scope evidence; no independent audio waveform timing measurement.'}
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n')
    print('PASS original inventory, exact installed/tested payload, cinematic branch, caption bounds and radio/TV inactive draw context')

if __name__=='__main__':main()
