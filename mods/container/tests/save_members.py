"""Read-only JSAV v117 member stream; no save or game writes."""
import re
import struct
import zlib
from pathlib import Path

def members(path):
    data=Path(path).read_bytes()
    if data[:8]!=b'JSAVu\0\0\0':raise ValueError('Unsupported save container')
    fields,capacity,tokens=struct.unpack_from('<3I',data,8);off=20+tokens+fields
    output={}
    while off<len(data):
        name=data[off:off+260].split(b'\0')[0].decode('ascii')
        if not re.fullmatch(r'[A-Za-z0-9_]+\.HL[123]',name) or name in output:raise ValueError('Unsafe/duplicate save member')
        size=struct.unpack_from('<I',data,off+260)[0];off+=264;raw=bytearray()
        if size>128*1024*1024:raise ValueError('Save member exceeds bound')
        while len(raw)<size:
            n=struct.unpack_from('<I',data,off)[0];off+=4
            if not 0<n<=len(data)-off:raise ValueError('Invalid compressed record')
            decoder=zlib.decompressobj();chunk=decoder.decompress(data[off:off+n]);off+=n
            if not decoder.eof or decoder.unused_data or not 0<len(chunk)<=524288 or len(raw)+len(chunk)>size:raise ValueError('Invalid compression boundary')
            raw.extend(chunk)
        output[name]=bytes(raw)
    if off!=len(data):raise ValueError('Save record boundary differs')
    return output
