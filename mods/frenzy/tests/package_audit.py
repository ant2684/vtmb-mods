"""Strict gameplay membership, CRC, clean-PE and exact certified byte gate."""
import argparse,hashlib,re,zipfile,tempfile,json
from pathlib import Path,PurePosixPath
from clean_pe import clean
EXPECTED={'Bin/loader/griffith-frenzy-werewolf-fix.vtm': 'FD5FF2E0003FA712A73A5D92B88575B7920F7003789F4B7F27CA1B9FF539D38A', 'Unofficial_Patch/maps/la_library_1.bsp': 'E92AF309033CE32CFBF97723D49FC6CCB7357F71CE79179B33980718080A966A', 'Unofficial_Patch/maps/sp_observatory_2.bsp': '6690798013DD82432A4C94F199111E35C5CA581BBC5AD351B0BA626FFEC05CB7'}
EXPORTS=['loaded_vampire']
p=argparse.ArgumentParser();p.add_argument('archive',type=Path);a=p.parse_args()
with zipfile.ZipFile(a.archive) as z:
 assert z.testzip() is None
 names=z.namelist();assert len(names)==len(set(names)) and set(names)==set(EXPECTED)|{'README.txt'},names
 for name in names:
  q=PurePosixPath(name);assert not q.is_absolute() and '..' not in q.parts and '\\' not in name
  raw=z.read(name)
  if name=='README.txt':
   text=raw.decode('ascii');assert not re.search(r'(?im)^verify\s*$|\.log\b|logging',text)
  else:
   assert hashlib.sha256(raw).hexdigest().upper()==EXPECTED[name],name
   if name.endswith('.vtm'):
    with tempfile.TemporaryDirectory(prefix='vtmb-package-audit-') as tmp:
     binary=Path(tmp)/'candidate.vtm';binary.write_bytes(raw);clean(binary,EXPORTS)
print('PASS CRC, exact payload membership/bytes, manual README and clean binary')
