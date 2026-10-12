"""Execute the supported native HealthHeal/HealthToPercent, not a Python heal.

Only the attribute service and stock profiling sink are fixtures. No live game.
"""
import argparse
import hashlib
import struct
from pathlib import Path
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP, UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP

PIN = 'c546f4de2003624d72f54d03805e0dbe1d8157231adcc62368ff53fe6e48a76f'
BASE, MEM, STACK = 0x10000000, 0x12000000, 0x13000000


def case(image, damage, aggravated, maximum, amount):
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    u.mem_map(BASE, (len(image) + 4095) & ~4095)
    u.mem_write(BASE, image)
    u.mem_map(MEM, 0x20000)
    u.mem_map(STACK, 0x10000)
    def write(at, value): u.mem_write(at, struct.pack('<I', value & 0xffffffff))
    def read(at): return struct.unpack('<I', u.mem_read(at, 4))[0]
    entity, groups, group, stop = MEM, MEM + 0x8000, MEM + 0x8100, MEM + 0xff00
    attrs = {15: damage, 16: aggravated, 17: maximum}
    writes = []
    write(entity, BASE + 0x4cf4d4)
    write(entity + 0x208, 100)  # stock accessor scales to this legacy maximum
    write(entity + 0x13bc, 1)
    write(entity + 0x13c0, groups)
    write(groups, group)
    write(group + 0x10, 0)
    write(BASE + 0x9f3680, MEM + 0x9000)
    write(BASE + 0x9f3620, MEM + 0xa000)
    def ret(value, pop):
        sp = u.reg_read(UC_X86_REG_ESP)
        u.reg_write(UC_X86_REG_EAX, value)
        u.reg_write(UC_X86_REG_EIP, read(sp))
        u.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
    def hook(uc, address, size, data):
        if address == stop:
            uc.emu_stop()
        elif address == BASE + 0x2012d0:
            assert uc.reg_read(UC_X86_REG_ECX) == group
            index = read(uc.reg_read(UC_X86_REG_ESP) + 4)
            ret(attrs[index], 4)
        elif address == BASE + 0x201100:
            assert uc.reg_read(UC_X86_REG_ECX) == group
            sp = uc.reg_read(UC_X86_REG_ESP)
            index, count = read(sp + 4), read(sp + 8)
            assert index in [15, 16]
            attrs[index] -= count
            writes.append((index, count))
            ret(0, 8)
    u.hook_add(UC_HOOK_CODE, hook)
    sp = STACK + 0xff00
    write(sp, stop); write(sp + 4, amount)
    u.reg_write(UC_X86_REG_ESP, sp)
    u.reg_write(UC_X86_REG_ECX, entity)
    for reg in [UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]:
        u.reg_write(reg, 0xabc123)
    u.emu_start(BASE + 0x33c340, stop, count=200000)
    assert u.reg_read(UC_X86_REG_EIP) == stop
    assert u.reg_read(UC_X86_REG_ESP) == sp + 8, 'thiscall ret4'
    for reg in [UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]:
        assert u.reg_read(reg) == 0xabc123, 'nonvolatile register'
    healed = min(max(amount, 0), damage) if 0 < damage < maximum else 0
    assert attrs[15] == damage - healed
    assert attrs[16] == min(aggravated, attrs[15])
    assert all(0 <= value <= maximum for value in [attrs[15], attrs[16]])
    if healed:
        # The actual Werewolf virtual+570 executed HealthToPercent and wrote +210.
        assert read(entity + 0x210) == (maximum - attrs[15]) * 100 // maximum
    return {'damage': damage, 'aggravated': aggravated, 'maximum': maximum,
            'amount': amount, 'healed': healed, 'native_cached_percent': read(entity + 0x210)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('server', type=Path)
    args = parser.parse_args()
    raw = args.server.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError('Unsupported server')
    image = pefile.PE(data=raw).get_memory_mapped_image()
    fixtures = [(100, 0, 900, 5), (100, 100, 900, 5), (100, 98, 900, 5),
                (3, 3, 900, 5), (0, 0, 900, 5), (900, 900, 900, 5),
                (100, 20, 1200, 5), (100, 20, 900, 0), (1, 0, 900, 1)]
    for fixture in fixtures:
        print(case(image, *fixture))
    print('PASS 9 native HealthHeal/current-attributes/Werewolf-virtual/ABI cases')


if __name__ == '__main__':
    main()
