"""Independent raw-trace and process-PCM audit; no game writes or input."""
import json,sys,hashlib,wave,math,argparse
from pathlib import Path
from correlate import pcm,match
parser=argparse.ArgumentParser();parser.add_argument('--session');parser.add_argument('--output');parser.add_argument('--assets');parser.add_argument('--plugin');opt=parser.parse_args()
work=Path(__file__).resolve().parents[2];session=Path(opt.session) if opt.session else work/'sessions/candidate_c';assets=Path(opt.assets) if opt.assets else work/'assets';binary=Path(opt.plugin) if opt.plugin else work/'source/build/subtitle-pause-fix.vtm'
period=18801792;radio_source=assets/'radio_loop_1.wav'
cache={}
def rows(path):return [json.loads(x) for x in path.read_text().splitlines()]
def traces(run,label):return rows(run/label/'trace.jsonl')
def radio(row):return next(c for c in row['channels'] if 'radio_loop_' in c['name'])
def native_sec(c):return c['sample_position']/c['sample_rate']
def correlation(run,label,wav,source,voice='radio',fraction=.5,phase=False):
 data=traces(run,label);index=min(len(data)-1,int(len(data)*fraction))
 # Keep the entire two-second waveform window inside this observed scenario.
 # A midpoint in a two-second save trace would include the following load.
 while index>0 and data[index]['qpc']+2>data[-1]['qpc']:index-=1
 row=data[index];qpc=row['qpc']
 assert qpc+2<=data[-1]['qpc']+.1,('Trace too short for a bounded audio match',label)
 channel=radio(row) if voice=='radio' else next(c for c in row['channels'] if 'newscaster' in c['name'])
 if voice=='tv':
  # Native story selection varies between runs. Match the observed recording,
  # never a hard-coded previous story. Decoded assets stay outside payloads.
  source=assets/(Path(channel['name']).stem+'.wav')
  assert source.exists(),('Decode the observed original TV asset before audit',channel['name'],source)
 packets=rows(Path(str(wav)+'.packets.jsonl'))[1:]
 packet=min(packets,key=lambda x:abs(x['qpc_100ns']/1e7-qpc))
 offset=round(packet['offset_frames']+(qpc-packet['qpc_100ns']/1e7)*44100)
 if wav not in cache:cache[wav]=pcm(wav)
 if source not in cache:cache[source]=pcm(source)
 rate,capture=cache[wav];sr,audio=cache[source];assert rate==sr==44100
 assert 0<=offset and offset+2*rate<=len(capture)
 fragment=capture[offset:offset+2*rate].copy();found=match(audio,fragment,rate)
 expected=(int(channel['sample_position'])%period)/rate if phase else native_sec(channel)
 error=found['source_seconds']-expected
 assert found['correlation']>.45 and abs(error)<.25,(label,found,expected,error)
 if voice=='radio':assert row['last_caption'].startswith('Radio: '),(label,row['last_caption'])
 else:assert row['last_caption'].startswith('Newscaster: '),(label,row['last_caption'])
 return {'label':label,'qpc':qpc,'capture_seconds':offset/rate,'native_seconds':expected,'source_asset':str(source),'heard':found,'error_seconds':error,'caption_index':channel['caption_index'],'visible_text':row['last_caption']}
report={'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest().upper(),'checks':[]}
tv=session/'runs/radio_tv_final';wait=session/'runs/radio_wait_final';controls=session/'runs/controls_bound'
report['checks'].append(correlation(tv,'radio_tv_on',tv/'radio_tv.wav',radio_source))
report['checks'].append(correlation(wait,'radio_wait_on',wait/'radio_wait.wav',radio_source))
for label in ('first_on','repeat_on','pause_resumed','tv_back_to_radio','radio_saved','radio_reloaded_on','radio_reloaded_repeat','returned_autosave'):
 report['checks'].append(correlation(controls,label,controls/'controls.wav',radio_source))
report['checks'].append(correlation(controls,'radio_to_tv',controls/'controls.wav',assets/'line11_col_e.wav',voice='tv'))
paused=traces(controls,'ordinary_pause');assert paused[-1]['qpc']-paused[0]['qpc']>=4.95
assert all(r['server_paused']==r['paused']==1 for r in paused)
assert max(r['server_time'] for r in paused)-min(r['server_time'] for r in paused)<.002
assert len({r['client_time'] for r in paused})==1
assert len({radio(r)['sample_position'] for r in paused})==len({radio(r)['caption_index'] for r in paused})==1
report['checks'].append({'label':'ordinary pause','result':'PASS','seconds':paused[-1]['qpc']-paused[0]['qpc'],'server_subframe_jitter':max(r['server_time'] for r in paused)-min(r['server_time'] for r in paused),'sample_position':radio(paused[0])['sample_position'],'caption_index':radio(paused[0])['caption_index']})
saved=radio(traces(controls,'radio_saved')[0]);reload_rows=traces(controls,'radio_reloaded_on');restored=radio(reload_rows[0])
assert native_sec(saved)>50 and native_sec(restored)<.1
assert traces(controls,'radio_reloaded_on')[0]['server_time']>50
assert saved['mixer']!=restored['mixer'] or saved['source']!=restored['source']
report['checks'].append({'label':'on-save reload recreates stream','result':'PASS','saved_source_seconds':native_sec(saved),'restored_source_seconds':native_sec(restored),'restored_world_time':reload_rows[0]['server_time']})
fresh=traces(controls,'changed_map');assert fresh[0]['server_time']<2 and not any('radio_loop_' in c['name'] for c in fresh[0]['channels'])
back=traces(controls,'returned_autosave');assert native_sec(radio(back[0]))<1
report['checks'].append({'label':'map then autosave has fresh radio epoch','result':'PASS'})
loop=session/'loop_final'
if not (loop/'runner-result.json').exists():
 report['result']='PENDING_LOOP';print(json.dumps(report,indent=2));sys.exit(0)
assert json.loads((loop/'runner-result.json').read_text())['result']=='PASS'
looprows=rows(loop/'trace.jsonl');after=[r for r in looprows if radio(r)['sample_position']/44100>427]
assert len(after)>20
for row in after:
 c=radio(row);phase=(int(c['sample_position'])%period)/44100;interval=c['caption_interval']
 assert interval['start']-.1<=phase<=interval['end']+.1 and row['last_caption'].endswith(interval['text'])
 # Each observed text is the actual native phrase/sentence entry for that phase.
assert after[0]['last_caption'].startswith('Radio: Hello LA')
# Use an ordinary trace subfolder for the shared correlation helper.
sub=loop/'after_wrap';sub.mkdir(exist_ok=True);(sub/'trace.jsonl').write_text('\n'.join(json.dumps(r) for r in after))
report['checks'].append(correlation(loop,'after_wrap',loop/'boundary.wav',radio_source,fraction=.25,phase=True))
report['checks'].append({'label':'real uninterrupted loop','result':'PASS','period_samples':period,'period_seconds':period/44100,'after_wrap_observations':len(after),'first_text':after[0]['last_caption'],'last_text':after[-1]['last_caption']})
report['result']='PASS';dest=Path(opt.output) if opt.output else work/'gameplay-verification.json';dest.write_text(json.dumps(report,indent=2));print(json.dumps({'result':'PASS','binary_sha256':report['binary_sha256'],'checks':len(report['checks']),'report':str(dest)}))
