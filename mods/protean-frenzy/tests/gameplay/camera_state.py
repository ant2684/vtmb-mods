"""Read the effective camera from the pinned client, using its native getter logic."""
import struct


def camera_state(reader):
    client = reader.modules['client.dll']
    assert reader.read(client + 0xffa20, 6).hex() == '8a81f8000000', 'Unsupported camera getter'
    input_ptr = reader.u(client + 0x27ba58)
    local = reader.u(client + 0x4a0d50)
    if not input_ptr or not local:
        return None
    native = reader.read(input_ptr, 0x1b9)
    easing = any(struct.unpack_from('<f', native, offset)[0] > 0 for offset in (0xfc, 0x108, 0x138, 0x100))
    return dict(raw=native[0xf0], force=native[0xf8], force_first=native[0xf9],
                third=int(bool(native[0xf0] or native[0xf8] or easing)), scene=reader.u(local + 0x16e0))
