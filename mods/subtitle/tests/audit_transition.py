"""Independent audit of the complete tutorial/Use/reload/Red Spot scenario."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from audit_startup import current_caption,channel,lines
from correlate import pcm,match
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'infra/common').is_dir());sys.path.insert(0,str(ROOT))
from infra.core import read_json,atomic_json,digest,require

def audit(outer,assets,plugin):
    receipt=read_json(outer/'observation-result.json');require(receipt['status']=='PASS','Whole scenario failed')
    require(read_json(outer/'restoration.json')['status']=='PASS','Files/settings not restored')
    require(receipt['plugin_sha256']==digest(plugin),'Final binary differs');folder=Path(receipt['evidence'])
    require(read_json(outer/'transaction/journal.json')['state']=='RESTORED','Transaction incomplete')
    report={'status':'PASS','plugin_sha256':digest(plugin),'evidence':str(folder),'checks':[]}
    dialogue=lines(folder/'tutorial-dialogue.jsonl');picks=[]
    for r in dialogue:
        if r['kind']=='pick_response':
            line=r['state']['line_ids'][r['chosen_index']]
            if not picks or picks[-1]!=line:picks.append(line)
    require(picks in ([12,26,1027,1033],[12,26,1027,1032]),'Tutorial native dialogue differs')
    require(sum(r['kind']=='skip_npc_speech' for r in dialogue)>0,'Speech skipping absent')
    report['checks'].append({'name':'native tutorial dialogue','picked_line_ids':picks})
    labels=[('apartment_initial_off',False),('apartment_first_use',True),('apartment_second_use',False),('apartment_third_use',True),('apartment_loaded_on',True),('redspot_initial_on',True),('redspot_resumed',True),('redspot_off',False),('redspot_on',True)]
    for label,audible in labels:
        rows=lines(folder/(label+'.jsonl'));require(rows[-1]['server_time']>rows[0]['server_time']+.5,'World frozen: '+label)
        for r in rows:
            radios=[e for e in r['entities'] if e['class']=='prop_radio'];require(len(radios)==1,'Radio entity ambiguous')
            require(radios[0]['fake_silence']==int(not audible) and radios[0]['active']==int(audible),'Wrong native switch/silence: '+label)
        delta=channel(rows[-1])['sample_position']-channel(rows[0])['sample_position']
        require(delta>20000 if audible else abs(delta)<=2048,'Wrong decoder progression: '+label)
        report['checks'].append({'name':label,'audible':audible,'decoder_delta':delta})
    uses=lines(folder/'physical-use.jsonl');require([r['label'] for r in uses[:3]]==['apartment_first_use','apartment_second_use','apartment_third_use'],'First Use result replaced or repeated')
    first=uses[0];s=first['before']['plugin_radios'][0];require(s['initial_pending']==2 and not s['seen_on'] and not s['armed'],'Early-off stream witness absent')
    require(s['epoch_valid'] and s['channel']==channel(first['before'])['channel'],'Pending stream binding absent')
    rows=lines(folder/'redspot_paused.jsonl');require(all(r['paused']==r['server_paused']==1 for r in rows),'Pause ownership absent')
    for key in ['server_time','client_time']:require(max(r[key] for r in rows)-min(r[key] for r in rows)<.02,'Paused clock advanced: '+key)
    require(max(channel(r)['sample_position'] for r in rows)-min(channel(r)['sample_position'] for r in rows)<=2048,'Paused decoder advanced')
    require(len({channel(r)['caption_index'] for r in rows})==1,'Paused captions advanced')
    report['checks'].append({'name':'Red Spot ordinary pause','duration':rows[-1]['qpc']-rows[0]['qpc']})
    trace=lines(folder/'transition.jsonl');origins={Path(r['name']).name:r for r in read_json(assets/'origins.json')}
    for label in ['apartment_first_audio','apartment_repeat_audio','apartment_loaded_audio','redspot_initial_audio','redspot_resumed_audio','redspot_repeat_audio']:
        packets=lines(folder/(label+'.wav.packets.jsonl'));require(packets[0]['pid']==read_json(folder/'process.json')['Id'],'Audio from other PID')
        packets=packets[1:];rate,capture=pcm(folder/(label+'.wav'));require(rate==44100,'Wrong captured PCM rate')
        begin=packets[0]['qpc_100ns']/1e7;end=packets[-1]['qpc_100ns']/1e7
        native=[r for r in trace if begin<=r['qpc']<=end and 'channels' in r]
        require(any(current_caption(r) for r in native),'Current visible native caption absent: '+label)
        name=Path(channel(native[len(native)//2])['name']).name;source=assets/name
        require(digest(source)==origins[name]['sha256'],'Source asset differs');sr,reference=pcm(source.with_suffix('.wav'))
        if sr!=rate:reference=np.interp(np.arange(round(len(reference)*rate/sr))*sr/rate,np.arange(len(reference)),reference)
        for start in [.5,2.5]:
            frame=round(start*rate);fragment=capture[frame:frame+2*rate];require(len(fragment)==2*rate,'Truncated capture')
            packet=next(p for p in packets if p['offset_frames']<=frame<p['offset_frames']+p['frames']);stamp=packet['qpc_100ns']/1e7+(frame-packet['offset_frames'])/rate
            row=min(native,key=lambda r:abs(r['qpc']-stamp));require(abs(row['qpc']-stamp)<.35,'PCM/native timestamp gap')
            found=match(reference,fragment,rate);c=channel(row);expected=c['sample_position']/c['sample_rate']+(stamp-row['qpc'])
            period=row['plugin_radios'][0]['raw'];period=int.from_bytes(bytes.fromhex(period)[92:96],'little',signed=True)
            if period>0:expected%=period/c['sample_rate']
            error=abs(found['source_seconds']-expected)
            require(found['correlation']>.35 and error<.8,'PCM/native phase mismatch '+label+' '+str(found)+' error '+str(error))
            report['checks'].append({'name':label,'capture_seconds':start,'source':name,'heard':found,'native_seconds':expected,'pipeline_seconds':error})
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--plugin',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.evidence,a.assets,a.plugin)
    except Exception as error:atomic_json(a.output,{'status':'FAIL','error':repr(error)});raise
    atomic_json(a.output,result);print(json.dumps(result,indent=2))
