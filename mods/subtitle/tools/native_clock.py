"""Position-independent x86 caption clock tied to the actual audio decoder."""
import struct

class Code:
    def __init__(self, va): self.va=va; self.b=bytearray(); self.labels={}; self.fixups=[]
    def emit(self, s): self.b.extend(bytes.fromhex(s))
    def i32(self, n): self.b.extend(struct.pack('<i', n))
    def label(self, n): self.labels[n]=self.va+len(self.b)
    def branch(self, op, target):
        self.emit(op); self.fixups.append((len(self.b), target)); self.emit('00000000')
    def ptr(self, reg, target):
        self.emit('e800000000'); anchor=self.va+len(self.b)
        self.emit({'edi':'5f8dbf','edx':'5a8d92'}[reg]); self.i32(target-anchor)
    def finish(self):
        for at,t in self.fixups:
            dst=self.labels[t] if isinstance(t,str) else t
            struct.pack_into('<i',self.b,at,dst-self.va-at-4)
        return bytes(self.b)

PAUSED=0x20314874
CLIENT_TIME=0x20314890
PLAT_IAT=0x20173324
GET_TIME=0x2001a6a0
GET_SAMPLE_POSITION=0x201383e0

def sync(va, state):
    # State: initialized (u32), paused (u32), pauseStart, totalPaused,
    # rawNow, logicalNow (all four times are float64).
    c=Code(va); c.emit('9c608bd8'); c.ptr('edi',state)
    c.emit('ff97'); c.i32(PLAT_IAT-state); c.emit('dd5f18')
    c.emit('85db0f95c30fb6db')
    c.emit('833f00'); c.branch('0f84','initialize')
    c.emit('3b5f04'); c.branch('0f84','calculate')
    c.emit('85db'); c.branch('0f85','start')
    c.emit('dd4718dc6708dc4710dd5f10')
    c.emit('895f04'); c.branch('e9','calculate')
    c.label('initialize'); c.emit('c70701000000d9eedd5f10')
    c.label('start'); c.emit('dd4718dd5f08895f04')
    c.label('calculate'); c.emit('837f0400'); c.branch('0f84','running')
    c.emit('dd4708'); c.branch('e9','finish_clock')
    c.label('running'); c.emit('dd4718')
    c.label('finish_clock'); c.emit('dc6710dd5f20619dc3')
    return c.finish()

def clock(va, state, sync_va):
    c=Code(va)
    # Radio now shares the proven decoder coordinate with TV and speech.
    # Existing non-radio bytes/guards and logical-clock fallback remain intact.
    c.emit('9c60')
    c.ptr('edx',state)
    c.emit('8b82'); c.i32(PAUSED-state); c.branch('e8',sync_va)
    c.emit('8b74243885f6'); c.branch('0f84','fallback')
    c.emit('f7869800000000000080'); c.branch('0f85','fallback')
    c.emit('8b7e0485ff'); c.branch('0f84','fallback')
    c.emit('8b1e85db'); c.branch('0f84','fallback')
    c.emit('8b8b0401000085c9'); c.branch('0f84','fallback')
    c.emit('8b19ff530c85c0'); c.branch('0f8e','fallback')
    c.emit('8be8')
    c.emit('8bce'); c.branch('e8',GET_SAMPLE_POSITION)
    c.emit('85c0'); c.branch('0f8c','fallback')
    # The callback returns the original position for every non-radio channel.
    # Radio wraps only its caption coordinate; decoding remains sequential.
    c.ptr('edx',state); c.emit('8b522885d2'); c.branch('0f84','convert')
    # Preserve the caller's complete x87 environment across the integer callback.
    c.emit('83ec6cdd3424555056ffd283c40cdd242483c46c')
    c.label('convert')
    c.emit('50db042455da3424d8869800000083c408619dc3')
    c.label('fallback')
    c.ptr('edx',state); c.emit('dd4220619dc3')
    return c.finish()

def pause_message(va, sync_va):
    c=Code(va); c.branch('e8',0x2003c190); c.branch('e8',sync_va); c.emit('c3'); return c.finish()
