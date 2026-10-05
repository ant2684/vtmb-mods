"""Reject payload debris and prove both archives preserve curated bytes."""
import argparse,hashlib,zipfile
from pathlib import Path,PurePosixPath
from verify import clean

def contents(path):
 with zipfile.ZipFile(path) as z:
  names=[n for n in z.namelist() if not n.endswith('/')]
  assert len(names)==len(set(names))
  for n in names:
   p=PurePosixPath(n);assert not p.is_absolute() and '..' not in p.parts and '\\' not in n
  return {n:z.read(n) for n in names}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('game_zip');ap.add_argument('source_zip');ap.add_argument('payload');ap.add_argument('source');ap.add_argument('binary');args=ap.parse_args()
 payload=Path(args.payload);source=Path(args.source);binary=Path(args.binary)
 clean(binary)
 game=contents(args.game_zip);capsule=contents(args.source_zip)
 assert set(game)=={'Bin/loader/history-stat-reset-fix.vtm','README.txt'}
 assert game['Bin/loader/history-stat-reset-fix.vtm']==binary.read_bytes()
 assert game=={p.relative_to(payload).as_posix():p.read_bytes() for p in payload.rglob('*') if p.is_file()}
 assert capsule=={p.relative_to(source).as_posix():p.read_bytes() for p in source.rglob('*') if p.is_file()}
 assert [n for n in capsule if PurePosixPath(n).name.lower().startswith('readme')]==['README.md']
 assert all(PurePosixPath(n).suffix.lower() not in ['.exe','.pdb','.lib','.exp','.log','.sav','.pyc'] for n in capsule)
 assert all('checksum' not in n.lower() and '__pycache__' not in n and '.zig-cache' not in n for n in capsule)
 assert game['Bin/loader/history-stat-reset-fix.vtm']==capsule['reference/history-stat-reset-fix.vtm']
 assert b'rollback' in game['README.txt'].lower() and b'copy' in game['README.txt'].lower()
 assert b'verify' not in game['README.txt'].lower() and b'checklist' not in game['README.txt'].lower()
 for path in [args.game_zip,args.source_zip]:print(Path(path).name,hashlib.sha256(Path(path).read_bytes()).hexdigest().upper())
 print('PASS exact archive bytes, path allowlists, clean payload and one README per archive')
if __name__=='__main__':main()
