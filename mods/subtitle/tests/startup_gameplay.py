"""Owned-process startup regression. Saves/config/video are restored transactionally.

Run with --config, --plugin and --output. --baseline observes the old failure;
the candidate run must satisfy initial on/off, switch, pause and reload checks.
No process memory writes, video-mode changes or plugin diagnostics are used.
"""
import argparse
import ctypes as C
import json
import os
import re
import queue
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'infra/common').is_dir())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from infra.core import atomic_json, digest, read_json, require
from infra.session import Transaction
from infra.gameplay import windows, preserve_session
from probe import Probe, k


class StartupProbe(Probe):
    def snap(self):
        row=super().snap();p=self.p;chat=p.u(p.modules['client.dll']+0x4cef90)
        row['chat_lines']=[]
        if chat:
            for i in range(6):
                ptr=p.u(chat+0x68+i*4)
                if not ptr:continue
                client=p.modules['client.dll'];require(p.u(ptr)==client+0x234d9c,'Unsupported native chat line')
                vp=p.u(ptr+4);texts=[];image=p.u(ptr+0x5c);capacity=length=0;address=0
                if image:
                    require(p.u(image)==p.modules['client.dll']+0x251994,'Unsupported native TextImage')
                    address=p.u(image+0x1c);capacity,length=struct.unpack('<HH',p.read(image+0x20,4))
                    require(length<=1023 and (not length or address),'Invalid native label text length')
                    if address:
                        require(capacity>=length+1,'Native label allocation too small')
                        raw=p.read(address,(length+1)*2);require(raw[-2:]==b'\0\0','Native label not terminated')
                        texts.append(raw[:-2].decode('utf-16-le'))
                row['chat_lines'].append({'line':ptr,'line_vtable':p.u(ptr),'image':image,'text_ptr':address,
                    'capacity':capacity,'length':length,'visible':p.read(vp+0x42,1)[0],'texts':texts})
        return row

    def command(self, text):
        require(text in {
            'map sm_pawnshop_1', 'map la_hub_1', 'map sm_apartment_1', 'map la_skyline_1', 'ent_fire tv_button Press',
            'ent_fire Radio2 Activate', 'ent_fire Radio2 Deactivate',
            'ent_fire newscaster SetFakeSilence 0', 'ent_fire newscaster SetFakeSilence 1',
            'ent_fire tv_screen ScriptUnhide', 'ent_fire tv_screen ScriptHide',
            'bind F11 pause', 'unbind F11',
        } or re.fullmatch(r'(save|load) rc_startup_(on|off)', text), 'Unregistered command')
        if not self.console():
            self.key(0x29); time.sleep(.5)
        require(self.console(), 'Console did not open')
        try:
            self.send(0x1d, 8); self.key(0x1e)
        finally:
            self.send(0x1d, 10, False)
        self.key(0x0e)
        for char in text:
            try:
                self.send(ord(char), 4); time.sleep(.025)
            finally:
                self.send(ord(char), 6, False)
        self.key(0x1c); time.sleep(.5)
        if self.console(): self.key(0x29)
        with (self.session/'commands.jsonl').open('a') as out:
            out.write(json.dumps({'qpc': time.perf_counter(), 'command': text})+'\n')


def radio(row):
    entities = [e for e in row['entities'] if e['class']=='prop_radio']
    require(len(entities)==1, 'Expected one radio in the selected map')
    channels = [c for c in row['channels'] if 'radio_loop_' in c['name']]
    require(len(channels)==1, 'Expected one radio stream')
    return entities[0], channels[0]


def record(probe, label, seconds=1):
    rows=[]; start=time.perf_counter()
    with (probe.session/(label+'.jsonl')).open('x') as out:
        while True:
            row=probe.snap();rows.append(row)
            out.write(json.dumps(row)+'\n');out.flush()
            if time.perf_counter()-start>=seconds: break
            time.sleep(.15)
    print(label, json.dumps({'time': rows[-1]['server_time'], 'caption': rows[-1]['last_caption'],
          'radios': [e['fake_silence'] for e in rows[-1]['entities'] if e['class']=='prop_radio']}), flush=True)
    return rows


def ready(probe, mapname, previous=None):
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        try:
            row=probe.snap();players=[e for e in row['entities'] if e['class']=='player']
            radios=[e for e in row['entities'] if e['class']=='prop_radio']
            if mapname in ['sm_apartment_1','la_skyline_1']:
                selected=any(e['class']=='npc_VNewscaster' for e in row['entities'])
            else:
                expected='Radio2' if mapname=='sm_pawnshop_1' else 'Radio1'
                selected=len(radios)==1 and probe.string(probe.p.u(radios[0]['entity']+0x26c),80)==expected
            if players and selected and not row['server_paused'] and not probe.console():
                handle=(players[0]['entity'], players[0]['serial'])
                if previous is None or previous!=handle:return row
        except (OSError,RuntimeError,AssertionError,ValueError): pass
        if probe.console(): probe.key(0x29)
        time.sleep(.25)
    raise RuntimeError('Map did not become ready: '+mapname)


def change(probe, command, mapname):
    old=next(e for e in probe.entities() if e['class']=='player')
    probe.command(command)
    return ready(probe,mapname,(old['entity'],old['serial']))


def advancing(rows, audible):
    first, last=rows[0],rows[-1];a,ca=radio(first);b,cb=radio(last)
    require(a['fake_silence']==b['fake_silence']==int(not audible),'Wrong radio state')
    require(last['server_time']>first['server_time']+.5,'World did not advance')
    delta=cb['sample_position']-ca['sample_position']
    require(delta>20000 if audible else abs(delta)<=2048,'Wrong decoder progression')
    if audible:
        require(any(caption_matches(r,radio(r)[1],'Radio: ') for r in rows),'No current radio caption in visible native UI')


def caption_matches(row,channel,prefix):
    interval=channel.get('caption_interval')
    if not interval or not interval['text']:return False
    phase=channel['sample_position']/channel['sample_rate']
    text=row['last_caption']
    visible=' '.join(value for line in row['chat_lines'] if line['visible'] for value in line['texts'])
    return (interval['start']-.1<=phase<=interval['end']+.1 and text.startswith(prefix)
            and text.endswith(interval['text']) and ' '.join(interval['text'].split()) in ' '.join(visible.split()))


def tv_channel(row):
    channels=[c for c in row['channels'] if 'newscaster' in c['name'].lower() and 'sample_position' in c]
    require(len(channels)==1,'Expected one active TV speech channel')
    return channels[0]


def capture(probe, helper, label, seconds=5):
    path=probe.session/(label+'.wav')
    child=subprocess.Popen([str(helper),str(probe.owned['Id']),str(probe.owned['Ticks']),str(path),str(seconds)],
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    lines=queue.Queue()
    threading.Thread(target=lambda:lines.put(child.stdout.readline()),daemon=True).start()
    ready=False
    try:
        line=lines.get(timeout=12);require(line.startswith('READY '),line);ready=True
        atomic_json(probe.session/(label+'.audio.json'), {'ready':line})
        rows=record(probe,label,seconds)
    finally:
        if not ready and child.poll() is None:child.kill()
        try:rest=child.communicate(timeout=15)[0]
        except subprocess.TimeoutExpired:
            child.kill();rest=child.communicate(timeout=5)[0]
        require(child.returncode==0,'Owned process audio capture failed: '+rest)
    return rows


def collect(probe, baseline, helper, tv_only=False):
    ready(probe,'la_skyline_1' if tv_only else 'sm_pawnshop_1')
    loaded=Path(probe.p.module_paths['subtitle-pause-fix.vtm'])
    atomic_json(probe.session/'loaded-plugin.json',{'path':str(loaded),'sha256':digest(loaded)})
    if tv_only:return collect_tv(probe,helper)
    first=record(probe,'initial',3)
    require(probe.p.u(radio(first[-1])[0]['entity']+0x204)&1,'Selected radio does not start on')
    if baseline:
        require(all(radio(r)[0]['fake_silence']==1 for r in first),'Old startup failure was not reproduced')
        return {'status':'PASS','scope':'old plugin reproduces start-on radio forced silent'}
    advancing(first,True)
    capture(probe,helper,'initial_audio',5)
    probe.command('ent_fire Radio2 Deactivate');advancing(record(probe,'off',3),False)
    probe.command('ent_fire Radio2 Activate');advancing(capture(probe,helper,'resumed_audio',5),True)
    probe.command('ent_fire Radio2 Activate');advancing(record(probe,'duplicate_on',2),True)
    probe.command('bind F11 pause');probe.key(0x57);time.sleep(.4)
    paused=record(probe,'paused',3)
    require(all(r['paused']==r['server_paused']==1 for r in paused),'Ordinary pause not established')
    require(abs(paused[-1]['server_time']-paused[0]['server_time'])<.02,'World advanced during pause')
    require(abs(radio(paused[-1])[1]['sample_position']-radio(paused[0])[1]['sample_position'])<=2048,'Radio advanced during pause')
    require(radio(paused[-1])[1]['caption_index']==radio(paused[0])[1]['caption_index'],'Captions advanced during pause')
    probe.key(0x57);time.sleep(.4);advancing(record(probe,'after_pause',2),True)
    probe.command('unbind F11')
    probe.command('save rc_startup_on');change(probe,'load rc_startup_on','sm_pawnshop_1')
    advancing(record(probe,'loaded_on',3),True)
    probe.command('ent_fire Radio2 Deactivate');probe.command('save rc_startup_off')
    change(probe,'load rc_startup_off','sm_pawnshop_1');advancing(record(probe,'loaded_off',3),False)
    probe.command('ent_fire Radio2 Activate');advancing(capture(probe,helper,'loaded_resume_audio',5),True)
    change(probe,'map la_hub_1','la_hub_1');defaultoff=record(probe,'default_off',2)
    require(not(probe.p.u(radio(defaultoff[-1])[0]['entity']+0x204)&1),'Selected radio does not start off')
    advancing(defaultoff,False)
    change(probe,'map sm_pawnshop_1','sm_pawnshop_1');advancing(record(probe,'fresh_return',3),True)
    change(probe,'map la_skyline_1','la_skyline_1')
    return collect_tv(probe,helper)


def collect_tv(probe,helper):
    # Fresh-map logic_auto, elevator and player-touch outputs can mute TV after
    # the scene becomes observable. Settle those stock events before one Press.
    record(probe,'tv_preparation',6)
    probe.command('ent_fire tv_button Press')
    tv=capture(probe,helper,'tv_audio',5)
    news=[e for e in tv[-1]['entities'] if e['class']=='npc_VNewscaster']
    require(len(news)==1 and news[0]['fake_silence']==0,'TV did not unmute')
    require(any('newscaster' in c['name'].lower() for r in tv for c in r['channels']),'TV channel missing')
    require(any(caption_matches(r,tv_channel(r),'Newscaster: ') for r in tv),'No current TV caption in visible native UI')
    probe.command('bind F11 pause');probe.key(0x57);time.sleep(.4);tvpause=record(probe,'tv_paused',3)
    require(all(r['paused']==r['server_paused']==1 for r in tvpause),'TV pause missing')
    require(abs(tvpause[-1]['server_time']-tvpause[0]['server_time'])<.02,'TV world pause failed')
    require(abs(tvpause[-1]['client_time']-tvpause[0]['client_time'])<.02,'TV client clock pause failed')
    before,after=tv_channel(tvpause[0]),tv_channel(tvpause[-1])
    require((before['mixer'],before['source'])==(after['mixer'],after['source']),'TV stream changed during pause')
    require(abs(after['sample_position']-before['sample_position'])<=2048,'TV audio advanced during pause')
    require(after['caption_index']==before['caption_index'],'TV caption index advanced during pause')
    require(tvpause[-1]['last_caption']==tvpause[0]['last_caption'],'TV caption changed during pause')
    probe.key(0x57);probe.command('unbind F11');resumed=record(probe,'tv_resumed',3)
    require(resumed[-1]['server_time']>resumed[0]['server_time']+.5 and all(r['server_paused']==0 for r in resumed),'TV world did not resume')
    require(any(tv_channel(b)['mixer']==tv_channel(a)['mixer'] and tv_channel(b)['sample_position']>tv_channel(a)['sample_position']+20000
                for a in resumed for b in resumed if b['qpc']>a['qpc']),'TV audio did not resume')
    return {'status':'PASS','scope':'TV stock button, visible current caption, process PCM, native audio/client/world/caption pause and audio/world resume'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--plugin',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audio-helper',type=Path);parser.add_argument('--baseline',action='store_true');parser.add_argument('--tv-only',action='store_true');args=parser.parse_args()
    config=read_json(args.config);game=Path(config['game_root']).resolve();args.output.mkdir(parents=True,exist_ok=False)
    require(args.plugin.is_file(),'Plugin input absent')
    require(not(args.baseline and args.tv_only),'Baseline and TV-only scopes are exclusive')
    if not args.baseline:require(args.audio_helper is not None and args.audio_helper.is_file(),'Build/select the external audio capture helper first')
    windows(config,'Inspect',args.output);require(not read_json(args.output/'settings-current.json')['Processes'],'User game running')
    cfg=(game/'Unofficial_Patch/cfg/config.cfg').read_text(encoding='cp1252')
    require(not re.search(r'bind\s+"?F11\b',cfg,re.I),'Preserve existing F11 binding; adapt probe')
    for stem in ['on','off']:require(not(game/f'Unofficial_Patch/save/rc_startup_{stem}.sav').exists(),'Task save name already exists')
    tx=Transaction(game,args.output/'transaction');folder=tx.start();probe=None;result={}
    try:
        windows(config,'Inspect',folder);atomic_json(folder/'settings.json',read_json(folder/'settings-current.json'))
        tx.watch_inventory()
        dirs=['Bin/loader','Unofficial_Patch/cfg','Vampire/cfg','Unofficial_Patch/save','Vampire/save',
              'Unofficial_Patch/python','Vampire/python','Unofficial_Patch/maps/graphs','Vampire/maps/graphs']
        for directory in dirs:
            for file in (game/directory).rglob('*'):
                if file.is_file():
                    relative=file.relative_to(game).as_posix();tx.preserve(relative)
                    if not directory.startswith('Bin/'):tx.allow_runtime(relative)
        for directory in ['','Vampire','Unofficial_Patch']:
            for file in (game/directory).glob('*'):
                if file.is_file() and file.suffix.lower() in ['.cfg','.log','.txt','.inf']:
                    tx.allow_runtime(file.relative_to(game).as_posix())
        for directory in ['Vampire','Unofficial_Patch']:
            for source in (game/directory/'python').rglob('*.py'):
                for ext in ['.pyc','.pyo']:tx.allow_runtime(source.with_suffix(ext).relative_to(game).as_posix())
            for name in ['console.log','logs/console.log']:tx.allow_runtime(directory+'/'+name)
            for mapname in ['sm_pawnshop_1','la_hub_1','sm_apartment_1','la_skyline_1']:
                for n in range(1,4):tx.allow_runtime(f'{directory}/save/{mapname}.HL{n}')
                for ext in ['loc','ain']:tx.allow_runtime(f'{directory}/maps/graphs/{mapname}.{ext}')
            tx.allow_runtime(directory+'/maps/graphs/.loc')
        for suffix in ['',*['%02d'%n for n in range(10)]]:tx.allow_runtime('Unofficial_Patch/save/autosave'+suffix+'.sav')
        for stem in ['on','off']:tx.allow_runtime('Unofficial_Patch/save/rc_startup_'+stem+'.sav')
        tx.allow_runtime('console.log')
        plugin_hash=digest(args.plugin);tx.write('Bin/loader/subtitle-pause-fix.vtm',args.plugin.read_bytes())
        launch=['-game','Unofficial_Patch','-dev','-novid','-console','+developer','0','+map','la_skyline_1' if args.tv_only else 'sm_pawnshop_1']
        atomic_json(folder/'launch.json',{'GameRoot':str(game),'Arguments':launch,'Candidates':[{'Path':str(game/'Bin/loader/subtitle-pause-fix.vtm'),'Hash':plugin_hash}]})
        tx.launch_intent(game/'Vampire.exe',launch);windows(config,'Launch',folder,folder/'launch.json')
        owned=read_json(folder/'process.json');tx.owned_process(owned['Id'],owned['Ticks'])
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            try:
                probe=StartupProbe(folder);probe.snap();break
            except (OSError,RuntimeError,AssertionError,KeyError):
                if probe:k.CloseHandle(probe.p.h);probe=None
                time.sleep(.4)
        require(probe is not None,'Game observer did not become ready')
        result=collect(probe,args.baseline,args.audio_helper,args.tv_only)
        require(read_json(folder/'loaded-plugin.json')['sha256']==plugin_hash,'Loaded different plugin')
        atomic_json(args.output/'observations-result.json',{**result,'plugin_sha256':plugin_hash,'evidence':str(folder)})
    except Exception as error:
        atomic_json(args.output/'result.json',{'status':'FAIL','error':repr(error),'evidence':str(folder)});raise
    finally:
        if probe:k.CloseHandle(probe.p.h)
        try:
            preserve_session(tx,config,folder)
            atomic_json(args.output/'restoration.json',{'status':'PASS','journal':str(tx.journal)})
        except Exception as error:
            atomic_json(args.output/'restoration.json',{'status':'FAIL','error':repr(error),'journal':str(tx.journal)})
            atomic_json(args.output/'result.json',{'status':'FAIL','stage':'restoration','error':repr(error),'evidence':str(folder)})
            raise
    atomic_json(args.output/'result.json',{**result,'restoration':'PASS','plugin_sha256':plugin_hash,'evidence':str(folder)})
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
