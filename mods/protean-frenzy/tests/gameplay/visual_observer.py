"""Read-only visual state for the supported client; never patches the renderer."""
import hashlib,struct
import pefile

def visual_state(reader):
    b=reader.modules['client.dll']
    def u(p):return reader.u(p)
    def ref(rva,indirect=False):
        wrapper=u(b+rva) if indirect else b+rva
        p=u(wrapper+4)
        return dict(float=struct.unpack('<f',reader.read(p+0x28,4))[0],integer=u(p+0x2c))
    p=u(b+0x4a0d50)
    result=dict(player=hex(p),health_ankh=u(b+0x3ede98),
        feedvision=ref(0x619060),mat_fullbright=ref(0x619928,True),
        intensity=ref(0x6191d0),blur_radius=ref(0x618b00),expand=ref(0x618ef0),dx6=ref(0x618dd0),
        stored_protean=u(b+0x61992c),saved_brightness=u(b+0x619930))
    if p:
        result['redvision_flag']=reader.read(p+0x14ec,1)[0]
        count=u(p+0x1178);table=u(p+0x117c)
        if count>64:raise RuntimeError('Invalid client discipline-object count')
        raw=[]
        for j in range(count):
            obj=u(table+4*j)
            if u(obj+0x10)==3:
                values=u(u(obj+8))
                raw.append(u(values+11*4))
        result['raw_protean']=raw
    return result

def verify_renderer(reader,game):
    path=game/'Vampire/cl_dlls/client.dll';raw=path.read_bytes();pe=pefile.PE(data=raw)
    b=reader.modules['client.dll'];delta=b-pe.OPTIONAL_HEADER.ImageBase
    memory=bytearray(pe.get_memory_mapped_image())
    for block in pe.DIRECTORY_ENTRY_BASERELOC:
        for entry in block.entries:
            if entry.type==3:
                struct.pack_into('<I',memory,entry.rva,(struct.unpack_from('<I',memory,entry.rva)[0]+delta)&0xffffffff)
    ranges=[(0x19f480,0x19f935),(0x19dbd0,0x19e1df),(0x50f60,0x50f6b)]
    for start,end in ranges:
        assert reader.read(b+start,end-start)==memory[start:end],('Renderer modified',hex(start))
    target=0x19f480;calls=[]
    for at in range(0x1000,0x260000):
        if memory[at]==0xe8 and at+5+struct.unpack_from('<i',memory,at+1)[0]==target:calls.append(hex(at))
    assert calls==['0x19e05d'],calls
    return dict(client_sha256=hashlib.sha256(raw).hexdigest(),unchanged_ranges=[[hex(s),hex(e)] for s,e in ranges],redvision_call_sites=calls)
