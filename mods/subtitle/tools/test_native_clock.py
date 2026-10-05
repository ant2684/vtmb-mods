"""Execute the x86 decoder clock, unchanged TV path and logical fallback."""
import math
import struct

try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import *
except ImportError as exc:
    raise SystemExit("This optional test requires the Python 'unicorn' package.") from exc

import native_clock as native


CODE = 0x60000000
STATE = CODE + 0x1000
DATA = 0x30000000
STACK = DATA + 0xf000
RESULT = DATA + 0x100
CHANNEL = DATA + 0x1000
MIXER = DATA + 0x2000
SFX = DATA + 0x3000
SOURCE = DATA + 0x4000
SOURCE_VTABLE = DATA + 0x5000
NOW_STUB = DATA + 0x6000
RATE_STUB = DATA + 0x6100
POSITION_STUB = DATA + 0x6200
RETURN_STUB = DATA + 0x6300
PHASE_STUB = DATA + 0x6400


def p32(value):
    return struct.pack("<I", value)


def f32(value):
    return struct.pack("<f", value)


class Harness:
    def __init__(self):
        self.u = Uc(UC_ARCH_X86, UC_MODE_32)
        self.u.mem_map(CODE, 0x2000)
        self.u.mem_map(DATA, 0x10000)
        self.u.mem_map(0x20000000, 0x400000)
        self.u.mem_write(CODE, native.sync(CODE, STATE))
        self.u.mem_write(CODE + 0x200, native.clock(CODE + 0x200, STATE, CODE))
        self.u.mem_write(NOW_STUB, bytes.fromhex("dd0500200030c3"))
        self.u.mem_write(RATE_STUB, bytes.fromhex("8b4104c3"))
        self.u.mem_write(POSITION_STUB, bytes.fromhex("8b8180000000c3"))
        self.u.mem_write(RETURN_STUB, bytes.fromhex("dd1d00010030dd1d08010030"))
        self.write32(native.PLAT_IAT, NOW_STUB)
        self.u.mem_write(native.GET_SAMPLE_POSITION,
                         bytes.fromhex("e9") + p32(POSITION_STUB - native.GET_SAMPLE_POSITION - 5))
        self.write32(CHANNEL, SFX)
        self.write32(CHANNEL + 4, MIXER)
        self.write32(CHANNEL + 0x54, 255)
        self.write32(SFX + 0x104, SOURCE)
        self.write32(SOURCE, SOURCE_VTABLE)
        self.write32(SOURCE + 4, 44100)
        self.write32(SOURCE_VTABLE + 0x0c, RATE_STUB)
        self.set_name('radio/radio_loop_1.mp3')
        self.set_caption_start(-1.0)
        self.set_sample_position(0)

    def write32(self, address, value):
        self.u.mem_write(address, p32(value))

    def set_now(self, value):
        self.u.mem_write(DATA + 0x2000, struct.pack("<d", value))

    def set_caption_start(self, value):
        self.u.mem_write(CHANNEL + 0x98, f32(value))

    def set_sample_position(self, value):
        self.write32(CHANNEL + 0x80, value)

    def set_name(self, value):
        self.u.mem_write(SFX, value.encode('ascii') + b'\0')

    def run(self):
        u = self.u
        registers = [UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
                     UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI,
                     UC_X86_REG_EBP]
        values = [0x1234, 0x2345, 0x3456, 0x4567, 0x5678, 0x6789, 0x789a]
        for register, value in zip(registers, values):
            u.reg_write(register, value)
        u.reg_write(UC_X86_REG_EFLAGS, 0x246)
        u.reg_write(UC_X86_REG_FPCW, 0x37f)
        u.reg_write(UC_X86_REG_ESP, STACK)
        u.mem_write(STACK + 0x10, p32(CHANNEL))
        trampoline = bytes.fromhex("d9e8e8") + p32(CODE + 0x200 - (DATA + 7)) + bytes.fromhex("e9") + p32(RETURN_STUB - (DATA + 12))
        u.mem_write(DATA, trampoline)
        u.ctl_remove_cache(DATA, RETURN_STUB + 0x20)
        u.emu_start(DATA, RETURN_STUB + 12, count=1000)
        assert u.reg_read(UC_X86_REG_ESP) == STACK
        for register, value in zip(registers, values):
            assert u.reg_read(register) == value
        assert u.reg_read(UC_X86_REG_EFLAGS) & 0x8d5 == 0x246 & 0x8d5
        old_x87 = struct.unpack("<d", u.mem_read(RESULT + 8, 8))[0]
        assert old_x87 == 1.0
        assert u.reg_read(UC_X86_REG_FPCW) == 0x37f
        return struct.unpack("<d", u.mem_read(RESULT, 8))[0]


def close(actual, expected):
    assert math.isclose(actual, expected, abs_tol=1e-6), (actual, expected)


def main():
    h = Harness()
    h.set_now(100.0)
    close(h.run(), 100.0)
    h.set_caption_start(100.0)
    h.set_sample_position(44100)
    h.set_now(101.0)
    close(h.run(), 101.0)
    h.set_now(130.0)
    close(h.run(), 101.0)  # captions follow the actual decoded sample coordinate
    h.write32(native.PAUSED, 1)
    close(h.run(), 101.0)
    h.set_now(160.0)
    close(h.run(), 101.0)  # decoder is frozen by ordinary game pause
    h.write32(native.PAUSED, 0)
    close(h.run(), 101.0)
    h.set_now(165.0)
    close(h.run(), 101.0)
    h.set_name('character/dlg/generic/newscaster/line1_col_e.mp3')
    close(h.run(), 101.0)  # non-radio retains 1.1.0 mixer-clock behavior
    h.set_sample_position(88200)
    close(h.run(), 102.0)
    h.set_name('tv/tv_loop_1.mp3')
    close(h.run(), 102.0)  # television remains on the same branch
    h.write32(CHANNEL + 0x54, 1)
    close(h.run(), 102.0)
    h.write32(CHANNEL + 4, 0)
    close(h.run(), 135.0)
    h.write32(CHANNEL + 4, MIXER)
    # Real generated PIC calls an integer callback which deliberately destroys
    # its x87 stack/environment. The helper must restore the incoming fld1.
    h.u.mem_write(PHASE_STUB, bytes.fromhex('dbe3d9eb8b44240831d2b9') + p32(18801792) + bytes.fromhex('f7f18bc2c3'))
    h.write32(STATE + 40, PHASE_STUB)
    h.set_sample_position(18801792 + 88200)
    close(h.run(), 102.0)
    h.set_sample_position(2 * 18801792)
    close(h.run(), 100.0)
    h.set_sample_position(18801791)
    close(h.run(), 100 + 18801791 / 44100)
    print("PASS: decoder coordinate, loop-phase callback, unchanged TV/speech, fallback, pause, ABI and full x87 preservation")


if __name__ == "__main__":
    main()
