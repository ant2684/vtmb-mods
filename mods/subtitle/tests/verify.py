"""Verify supported images, unique whole-instruction anchors and exact payload."""
import sys,json,hashlib,re,subprocess,argparse,os
from pathlib import Path
import pefile,capstone
from clean_payload import verify_clean
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--game',default=r'LOCAL_GAME_ROOT_REQUIRED');parser.add_argument('--plugin',default=str(ROOT/'build/subtitle-pause-fix.vtm'));opt=parser.parse_args();GAME=Path(opt.game)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
supported={'Bin/engine.dll':'9D00B2C1E5EDBAD052FB0B514634BA54574666E12D1B408C46CE141D51ED2313','Vampire/dlls/vampire.dll':'C546F4DE2003624D72F54D03805E0DBE1D8157231ADCC62368FF53FE6E48A76F'}
anchors=[('Bin/engine.dll',0x1188b0,'8b11ff5238d95c24048b74241085f6',0,5),('Bin/engine.dll',0x2d130,'e85bf0000085c0a3',0,5),('Vampire/dlls/vampire.dll',0x22c50d,'8bcee8124dddff83be4c070000ff',2,5),('Vampire/dlls/vampire.dll',0x22c803,'6a018bcee86860ddff',4,5)]
dis=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);report={'supported':{},'anchors':[],'checks':[]}
for n,h in supported.items():assert sha(GAME/n)==h;report['supported'][n]=h
for n,rva,signature,delta,length in anchors:
 pe=pefile.PE(str(GAME/n));sig=bytes.fromhex(signature);hits=[]
 for s in pe.sections:
  if not s.Characteristics&0x20000000:continue
  raw=s.get_data();start=0
  while True:
   pos=raw.find(sig,start)
   if pos<0:break
   hits.append(s.VirtualAddress+pos);start=pos+1
 assert hits==[rva],(n,hits)
 instructions=list(dis.disasm(pe.get_data(rva+delta,length),pe.OPTIONAL_HEADER.ImageBase+rva+delta));assert sum(i.size for i in instructions)==length
 report['anchors'].append({'image':n,'rva':hex(rva+delta),'instructions':[i.mnemonic+' '+i.op_str for i in instructions]})
loop_code=(ROOT/'plugin/radio_loop.h').read_text()
for name,image,rva in [('process_signature','Bin/mssmp3.asi',0x5ad0),('byte_loop_signature','Bin/engine.dll',0x137b93)]:
 array=re.search(r'\b'+name+r'\[\]\s*=\s*\{([^}]+)\}',loop_code).group(1)
 sig=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',array));p=pefile.PE(str(GAME/image))
 assert p.get_data(rva,len(sig))==sig,(name,'source guard disagrees with supported image')
 hits=[]
 for s in p.sections:
  if not s.Characteristics&0x20000000:continue
  raw=s.get_data();start=0
  while (at:=raw.find(sig,start))>=0:hits.append(s.VirtualAddress+at);start=at+1
 assert hits==[rva],(name,hits)
 report['checks'].append({'result':'PASS','guard':name,'image':image,'rva':hex(rva),'sha256':sha(GAME/image)})
binary=Path(opt.plugin);pe=pefile.PE(str(binary));assert pe.FILE_HEADER.Machine==0x14c and pe.OPTIONAL_HEADER.Magic==0x10b
report['checks'].append(verify_clean(binary, ['loaded_engine','loaded_vampire'], ROOT/'plugin'))
header=(ROOT/'plugin/generated_clock.h').read_text();array=header.split('kClockCode')[1].split('{',1)[1].split('}',1)[0];blob=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',array));assert binary.read_bytes().count(blob)==1
for args in ([str(ROOT/'tests/load_clean.exe'),str(binary.resolve()),'loaded_engine'],[str(ROOT/'tests/native_harness.exe')],[sys.executable,str(ROOT/'tools/test_native_clock.py')],[sys.executable,str(ROOT/'tests/dispatcher_harness.py')]):
 env=os.environ.copy();env['VTMB_VERIFY_GAME']=str(GAME)
 run=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env)
 assert run.returncode==0,run.stdout;report['checks'].append({'command':Path(args[-1]).name,'output':run.stdout,'result':'PASS'})
report.update(result='PASS',binary=str(binary),hash=sha(binary),size=binary.stat().st_size)
dest=ROOT/'build/technical-verification.json';dest.write_text(json.dumps(report,indent=2));print(json.dumps({'result':'PASS','hash':report['hash'],'size':report['size'],'certificate':str(dest)}))
