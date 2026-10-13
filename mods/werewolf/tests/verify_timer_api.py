"""Read-only stock datamap qualification; not a live Python/gameplay test."""
import hashlib
import struct
import sys
from pathlib import Path
import pefile

PIN = 'c546f4de2003624d72f54d03805e0dbe1d8157231adcc62368ff53fe6e48a76f'


def verify(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError('Unsupported server: API qualification refused')
    pe = pefile.PE(data=raw)
    memory = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    # Exact external-name fields of the supported class typedescription arrays.
    fields = {
        'timer': {0x575f84: 'Enable', 0x575fb0: 'Disable', 0x57608c: 'OnTimer'},
        'relay': {0x5791b8: 'Trigger', 0x5791e4: 'OnTrigger'},
        'auto': {0x575ac0: 'OnMapLoad'},
    }
    for kind, table in fields.items():
        for descriptor, expected in table.items():
            pointer = struct.unpack_from('<I', memory, descriptor)[0] - base
            name = memory[pointer:pointer+64].split(b'\0', 1)[0].decode('ascii')
            if name != expected:
                raise AssertionError((kind, hex(descriptor), expected, name))
            # Input descriptions include an executable native handler pointer.
            if not expected.startswith('On'):
                function = struct.unpack_from('<I', memory, descriptor+8)[0] - base
                if not any(s.Characteristics & 0x20000000 and
                           s.VirtualAddress <= function < s.VirtualAddress+s.Misc_VirtualSize
                           for s in pe.sections):
                    raise AssertionError('Input has no executable handler')
    for absent in (b'FireUser1\0', b'FireUser2\0', b'OnUser1\0', b'OnUser2\0', b'OnMapSpawn\0'):
        if absent in memory:
            raise AssertionError('Re-qualify previously unsupported API')
    print('PASS pinned stock timer Enable/Disable/OnTimer and relay Trigger/OnTrigger datamaps')


if __name__ == '__main__':
    verify(sys.argv[1])
