"""Reject service material in an ordinary deliverable, without changing bytes."""
import argparse,hashlib,json,re,sys
from pathlib import Path
import pefile

def clean(plugin,exports,source=None):
 raw=Path(plugin).read_bytes();p=pefile.PE(data=raw)
 assert p.FILE_HEADER.Machine==0x14c and p.OPTIONAL_HEADER.Magic==0x10b
 assert p.FILE_HEADER.Characteristics&0x2000,'Not a DLL'
 assert not p.FILE_HEADER.PointerToSymbolTable and not p.FILE_HEADER.NumberOfSymbols
 assert not p.OPTIONAL_HEADER.DATA_DIRECTORY[6].Size and not p.OPTIONAL_HEADER.DATA_DIRECTORY[6].VirtualAddress
 assert p.get_overlay_data_start_offset() is None,'Overlay remains'
 sections=[s.Name.rstrip(b'\0').decode() for s in p.sections]
 assert set(sections)<={'.text','.rdata','.data','.tls','.reloc'},sections
 assert {s.name.decode() for s in p.DIRECTORY_ENTRY_EXPORT.symbols}==set(exports)
 imports={i.name.decode() for d in getattr(p,'DIRECTORY_ENTRY_IMPORT',[]) for i in d.imports if i.name}
 forbidden={'CreateFileA','CreateFileW','WriteFile','fopen','fprintf','OutputDebugStringA','OutputDebugStringW','CreateThread','SendInput','CreateProcessA','CreateProcessW','RegSetValueExA','RegSetValueExW'}
 assert not imports&forbidden,imports&forbidden
 strings=re.findall(rb'[\x20-\x7e]{5,}',raw)+[x.decode('utf-16le').encode() for x in re.findall(rb'(?:[\x20-\x7e]\x00){5,}',raw)]
 for s in strings:
  assert not any(mark in s.lower() for mark in [b'.pdb',b'.log',b'console-task-command',b'console-input-command',b'test_hook',b'.debug',b'.buildid']),s
 if source:
  native='\n'.join(f.read_text() for f in Path(source).glob('*.[ch]'))
  assert not re.search(r'\b(?:log_status|log_line|trace|printf|fprintf|fopen|CreateFile[AW]|WriteFile|GetTickCount|OutputDebugString[AW])\s*\(',native)
  assert not any(mark in native for mark in ['CONSOLE_QA','CONSOLE_DIAGNOSTICS','observe_wolf_set_origin','diagnostic.log'])
 return {'result':'PASS','hash':hashlib.sha256(raw).hexdigest().upper(),'bytes':len(raw),'sections':sections,'imports':sorted(imports),'exports':sorted(exports)}

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('plugin');ap.add_argument('--exports',nargs='+',required=True);ap.add_argument('--source');ap.add_argument('--output');a=ap.parse_args()
 r=clean(a.plugin,a.exports,a.source)
 if a.output:Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps(r))
