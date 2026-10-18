"""Independent PCM/native-caption audit for startup_gameplay.py evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'infra/common').is_dir())
sys.path.insert(0,str(ROOT))
from infra.core import atomic_json, digest, read_json, require
from correlate import pcm, match


def lines(path):return [json.loads(line) for line in path.read_text().splitlines() if line]


def channel(row,voice='radio'):
    found=[c for c in row['channels'] if ('radio_loop_' if voice=='radio' else 'newscaster') in c['name'].lower()]
    require(len(found)==1,'Speech channel identity ambiguous')
    return found[0]


def current_caption(row,voice='radio'):
    c=channel(row,voice);interval=c.get('caption_interval');text=row['last_caption']
    if not interval or not interval['text']:return False
    phase=c['sample_position']/c['sample_rate']
    visible=' '.join(value for line in row['chat_lines'] if line['visible'] for value in line['texts'])
    return (interval['start']-.1<=phase<=interval['end']+.1 and text.startswith('Radio: ' if voice=='radio' else 'Newscaster: ')
            and text.endswith(interval['text']) and ' '.join(interval['text'].split()) in ' '.join(visible.split()))


def audit(evidence, assets, plugin, scope='all'):
    receipt=read_json(evidence/'result.json')
    if scope!='radio':require(receipt['status']=='PASS' and receipt['restoration']=='PASS','Gameplay/restoration did not finish')
    require(read_json(evidence/'restoration.json')['status']=='PASS','Restoration receipt absent')
    session=Path(receipt['evidence']);loaded=read_json(session/'loaded-plugin.json')
    require(digest(plugin)==loaded['sha256'],'Final plugin identity differs')
    if receipt.get('plugin_sha256'):require(digest(plugin)==receipt['plugin_sha256'],'Receipt plugin differs')
    origins={Path(row['name']).name:row for row in read_json(assets/'origins.json')}
    report={'status':'PASS','scope':scope,'collector_result':receipt,'plugin_sha256':digest(plugin),'checks':[]}
    audio_labels=(['initial_audio','resumed_audio','loaded_resume_audio'] if scope=='radio' else ['tv_audio'] if scope=='tv' else ['initial_audio','resumed_audio','loaded_resume_audio','tv_audio'])
    for label in audio_labels:
        voice='tv' if label=='tv_audio' else 'radio'
        trace=lines(session/(label+'.jsonl'));packets=lines(session/(label+'.wav.packets.jsonl'))[1:]
        require(all(row['pid']==read_json(session/'process.json')['Id'] for row in trace),'Trace PID differs')
        require(any(current_caption(row,voice) for row in trace),'Current native visible caption absent: '+label)
        names={Path(channel(row,voice)['name']).name for row in trace};require(len(names)==1,'Asset changed during fragment')
        name=next(iter(names));source=assets/name;require(name in origins and digest(source)==origins[name]['sha256'],'Source MP3 identity differs')
        sr,reference=pcm(source.with_suffix('.wav'));rate,capture=pcm(session/(label+'.wav'))
        require(rate==44100 and sr in [22050,44100,48000],'Wrong PCM rate')
        if sr!=rate:
            reference=np.interp(np.arange(round(len(reference)*rate/sr))*sr/rate,np.arange(len(reference)),reference)
        for start in [.5,2.5]:
            frame=int(start*rate);fragment=capture[frame:frame+int(2*rate)]
            require(len(fragment)==2*rate,'Audio fragment truncated')
            packet=next((p for p in packets if p['offset_frames']<=frame<p['offset_frames']+p['frames']),None)
            require(packet is not None,'No timestamped process PCM packet')
            stamp=packet['qpc_100ns']/1e7+(frame-packet['offset_frames'])/rate
            native=min(trace,key=lambda row:abs(row['qpc']-stamp));require(abs(native['qpc']-stamp)<.35,'Native/PCM sample too far apart')
            found=match(reference,fragment,rate)
            native_channel=channel(native,voice)
            expected=native_channel['sample_position']/native_channel['sample_rate']+(stamp-native['qpc'])
            error=abs(found['source_seconds']-expected)
            require(found['correlation']>.35 and error<.8,'PCM/native coordinates disagree: '+label+' '+str(found)+' error='+str(error))
            report['checks'].append({'label':label,'capture_seconds':start,'source':name,'heard':found,'native_seconds':expected,'error_seconds':error})
    radio_labels=[] if scope=='tv' else [('initial',True),('off',False),('duplicate_on',True),('loaded_on',True),('loaded_off',False),('default_off',False),('fresh_return',True)]
    for label,audible in radio_labels:
        trace=lines(session/(label+'.jsonl'));first,last=trace[0],trace[-1]
        states=[e['fake_silence'] for row in trace for e in row['entities'] if e['class']=='prop_radio']
        require(states and all(value==int(not audible) for value in states),'Wrong observed state: '+label)
        require(last['server_time']>first['server_time']+.5,'World frozen: '+label)
        delta=channel(last)['sample_position']-channel(first)['sample_position']
        require(delta>20000 if audible else abs(delta)<=2048,'Wrong decoder progression: '+label)
        if audible:require(any(current_caption(row) for row in trace),'Missing visible current caption: '+label)
        report['checks'].append({'label':label,'audible':audible,'decoder_delta':delta})
    if scope!='tv':
        paused=lines(session/'paused.jsonl')
        require(all(row['server_paused']==row['paused']==1 for row in paused),'Radio pause missing')
        require(max(channel(r)['sample_position'] for r in paused)-min(channel(r)['sample_position'] for r in paused)<=2048,'Radio advanced during pause')
        require(len({channel(r)['caption_index'] for r in paused})==1,'Radio captions advanced during pause')
        report['checks'].append({'label':'radio pause','samples':channel(paused[0])['sample_position']})
    if scope=='radio':return report
    paused=lines(session/'tv_paused.jsonl');resumed=lines(session/'tv_resumed.jsonl')
    require(all(row['server_paused']==row['paused']==1 for row in paused),'TV pause missing')
    require(len({(channel(r,'tv')['mixer'],channel(r,'tv')['source']) for r in paused})==1,'TV stream changed during pause')
    require(max(channel(r,'tv')['sample_position'] for r in paused)-min(channel(r,'tv')['sample_position'] for r in paused)<=2048,'TV decoded during pause')
    require(len({channel(r,'tv')['caption_index'] for r in paused})==1,'TV captions advanced during pause')
    require(all(r['server_paused']==0 for r in resumed) and resumed[-1]['server_time']>resumed[0]['server_time']+.5,'TV world did not resume')
    require(any(channel(b,'tv')['mixer']==channel(a,'tv')['mixer'] and channel(b,'tv')['sample_position']>channel(a,'tv')['sample_position']+20000
                for a in resumed for b in resumed if b['qpc']>a['qpc']),'TV audio did not resume')
    report['checks'].append({'label':'TV pause/resume','samples':channel(paused[0],'tv')['sample_position']})
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--assets',type=Path,required=True);parser.add_argument('--plugin',type=Path,required=True)
    parser.add_argument('--scope',choices=['all','radio','tv'],default='all')
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=audit(args.evidence,args.assets,args.plugin,args.scope);atomic_json(args.output,result)
    print(json.dumps(result,indent=2))
