"""Read-only observer of the supported native creation Sheet category counters."""
import struct

CATEGORIES=('physical','social','mental','talents','skills','knowledges','disciplines')

def observe(process):
    client=process.modules['client.dll']
    character=process.u(client+0x5fb14c)
    # The stock Sheet initializer publishes &Sheet.attributes at this global.
    attributes=process.u(client+0x5fb6e8)
    if not attributes:
        return {'initialized':False}
    sheet=attributes-0xc0
    pairs=struct.unpack('<14i',process.read(sheet+0x7c,56))
    return {'initialized':True,'sheet':sheet,
            'categories':{name:{'category_id':pairs[2*i],'remaining':pairs[2*i+1]}
                          for i,name in enumerate(CATEGORIES)},
            'remaining':[pairs[2*i+1] for i in range(7)],
            'spent':process.u(sheet+0x2e4),
            'auto_level':process.read(sheet+0x434,1)[0],
            'creation_mode':bool(character and process.u(character+0x274)),
            'auto_button':process.u(sheet+0x2dc),
            'reset_button':process.u(sheet+0x2d8)}
