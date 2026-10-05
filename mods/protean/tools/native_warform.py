"""Position-independent x86 hooks. All addresses refer to the pinned baseline."""
import struct

class Code:
    def __init__(self, va):
        self.va=va; self.b=bytearray(); self.labels={}; self.fixups=[]
    def emit(self, value): self.b.extend(bytes.fromhex(value))
    def label(self, name): self.labels[name]=self.va+len(self.b)
    def jump(self, opcode, target):
        op=bytes.fromhex(opcode); self.b.extend(op)
        self.fixups.append((len(self.b),target)); self.b.extend(b'\0'*4)
    def global_ptr(self, target, deref=False):
        # EDX := &global or *global, without an absolute VA or new PE relocation.
        self.emit('e8000000005a')
        anchor=self.va+len(self.b)-1
        self.emit('8b92' if deref else '8d92')
        self.b.extend(struct.pack('<i',target-anchor))
    def finish(self):
        for at,t in self.fixups:
            dst=self.labels[t] if isinstance(t,str) else t
            struct.pack_into('<i',self.b,at,dst-(self.va+at+4))
        return bytes(self.b)

def reentry(va):
    c=Code(va)
    c.emit('83b86c14000000') # cmp player.frenzyCount,0
    c.jump('0f8f',0x1033e9d4) # existing epilogue; no argument pushed yet
    c.emit('689f860100')      # displaced push 99999
    c.jump('e9',0x1033e9c3)
    return c.finish()

def input_owner(va):
    c=Code(va)
    c.emit('83bf6c14000000') # player Frenzy counter
    c.jump('0f8f','frenzy')
    c.emit('388fdc1e0000')   # original cmp byte [edi+1edc],cl
    c.jump('e9',0x103510dd)
    c.label('frenzy')
    c.emit('39c9')          # ZF=1: clear all player input, as ordinary Frenzy
    c.jump('e9',0x103510dd)
    return c.finish()

def feat_owner(va, extra=False):
    # CVFeat evaluation takes a CBaseCombatCharacter pointer as its sole argument.
    # A Frenzy shadow has default NPC traits, not the player's active Warform.
    # Evaluate the player's existing effects, once, only for their active beast AI.
    c=Code(va)
    c.emit('9c60') # preserve flags and all registers; argument now at esp+40
    c.emit('837c242800'); c.jump('0f84','done')
    c.jump('e8',0x101193b0) # UTIL_GetLocalPlayer, combat-character wrapper
    c.emit('85c0'); c.jump('0f84','done')
    c.emit('8bf08b88a800000085c9'); c.jump('0f84','done')
    c.emit('83b96c14000000'); c.jump('0f8e','done')
    c.emit('80b9dc1e000000'); c.jump('0f84','done')
    c.emit('8b81b01d000083f8ff'); c.jump('0f84','done')
    c.global_ptr(0x10566458,True)
    c.emit('8bc881e1ff1f0000c1e80d8d0c498d4c8a04394104')
    c.jump('0f85','done')
    c.emit('8b3985ff'); c.jump('0f84','done')
    c.global_ptr(0x104b2184) # exact pinned CNPC_VFrenzyShadow vtable
    c.emit('3917'); c.jump('0f85','done')
    c.emit('8b879c0000003b442428'); c.jump('0f85','done')
    c.emit('89742428') # evaluate the player's existing traits and effects
    c.label('done'); c.emit('619d')
    c.emit('83ec0c8b542410' if extra else '83ec105356')
    c.jump('e9',0x101e5b37 if extra else 0x101e56e5)
    return c.finish()

def extra_feat_owner(va):
    return feat_owner(va,True)

def expire(va):
    c=Code(va)
    c.emit('8bbda8000000') # displaced mov edi,[ebp+a8]: player
    c.emit('85ff'); c.jump('0f84','original')
    c.emit('83bf6c14000000'); c.jump('0f8e','original')
    # Resolve the existing controller handle, including its serial validation.
    c.emit('8b87b01d000083f8ff'); c.jump('0f84','original')
    c.global_ptr(0x10566458,True)
    c.emit('8bc881e1ff1f0000c1e80d8d0c498d4c8a04394104')
    c.jump('0f85','original')
    c.emit('8b3185f6'); c.jump('0f84','original')
    # Restore both visible player and active AI to the saved human model.
    # Keep the controller, Frenzy count, effect and remaining Frenzy time.
    c.emit('c687dc1e000000') # wolf = false
    c.emit('8d87d4230000508bcf8b17ff92a4010000')
    c.emit('8d87d4230000508bce8b16ff92a4010000')
    c.global_ptr(0x1070b228,True)
    c.emit('8b420c8987681c0000') # native post-morph timestamp
    # Same lifecycle event as the ordinary reverse-morph path.
    c.emit('6a0257')
    c.global_ptr(0x10750cb4)
    c.emit('8bca')
    c.jump('e8',0x10227a30)
    c.jump('e9',0x101f8fa3) # common trait-removal continuation, EBX reset there
    c.label('original'); c.jump('e9',0x101f917d)
    return c.finish()
