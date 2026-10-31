"""Run native GetHealthPct on a private read-only process-memory clone.

Writes performed by emulation affect the clone only. Demand-loaded pages are
asynchronous samples, not event-time damage records. No process write or injection.
"""
import struct
from pathlib import Path
import json
import sys
from local_runtime import CONFIG
sys.path.insert(0,CONFIG['native_dependencies'])
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_MEM_UNMAPPED
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EAX, UC_X86_REG_ESP

def emulate(read, base, entity, rva, arguments=()):
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    stack, stop = 0x7f000000, 0x7f001000
    uc.mem_map(stack, 0x2000)
    uc.mem_write(stack+0xff0, struct.pack('<I', stop))
    if arguments: uc.mem_write(stack+0xff4, struct.pack('<'+'I'*len(arguments), *arguments))
    pages = set()
    def missing(uc, access, address, size, value, userdata):
        first, last = address&~4095, (address+size-1)&~4095
        for page in range(first, last+1, 4096):
            if page in pages: return False
            data = read(page, 4096)
            uc.mem_map(page, 4096); uc.mem_write(page, data); pages.add(page)
        return True
    uc.hook_add(UC_HOOK_MEM_UNMAPPED, missing)
    uc.reg_write(UC_X86_REG_ECX, entity)
    uc.reg_write(UC_X86_REG_ESP, stack+0xff0)
    uc.emu_start(base+rva, stop, timeout=100000, count=20000)
    if uc.reg_read(UC_X86_REG_ESP) != stack+0xff4+4*len(arguments):
        raise RuntimeError('Incomplete native observer emulation')
    return uc, uc.reg_read(UC_X86_REG_EAX)

def native_health(read, base, entity):
    _, value = emulate(read, base, entity, 0x32fe60)
    return struct.unpack('<i', struct.pack('<I', value))[0]

def native_sequence(read, base, entity, sequence):
    uc, pointer = emulate(read, base, entity, 0x8fe80, (sequence,))
    # The returned label resides in a demand-loaded model page, hence use clone
    # bytes when present, otherwise read its immutable model string externally.
    try: raw=bytes(uc.mem_read(pointer,100))
    except Exception: raw=read(pointer,100)
    return raw.split(b'\0')[0].decode('ascii')
