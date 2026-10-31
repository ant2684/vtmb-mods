"""Read actual trait-effect membership, independent of capped feat values."""
import struct

def actor_effects(read,base,actor):
    def u(at):return struct.unpack('<I',read(at,4))[0]
    manager=base+0x74df78;table=u(manager+8);total=u(manager+4)
    if not table or total>4096:raise RuntimeError('Effect catalog unavailable')
    def groups(address):
        count=u(address)
        if count>64:raise RuntimeError('Effect membership unavailable')
        result=[]
        for index in range(count):
            identity=u(address+4+index*4)
            if identity>=total:raise RuntimeError('Effect identity outside catalog')
            entry=u(table+identity*4);name=u(entry+8)
            text=read(name,128).split(b'\0')[0].decode('ascii',errors='replace').lower()
            result.append([identity,text])
        return result
    return dict(groups=groups(actor+0x13dc),effective_groups=groups(u(actor+0x13c8)))
