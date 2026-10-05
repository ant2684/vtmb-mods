"""Strict gameplay membership, CRC, clean-PE and exact certified byte gate."""
import argparse,hashlib,re,zipfile,tempfile,json
from pathlib import Path,PurePosixPath
from clean_pe import clean
EXPECTED={'Bin/loader/console-pause-fix.vtm': '9919EBFC7A0661F26C3EA1F203139BEA39AB5C4E24252312072315965945B1FA'}
EXPORTS=['loaded_gameui']
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
