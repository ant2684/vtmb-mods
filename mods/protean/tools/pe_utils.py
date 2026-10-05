"""Minimal PE32 helpers used by the reproducible patch builder."""

from __future__ import annotations

import struct


IMAGE_BASE = 0x10000000


def p16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", data, offset, value)


def p32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


class Code:
    def __init__(self, va: int):
        self.va = va
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, int | str]] = []

    @property
    def current_va(self) -> int:
        return self.va + len(self.data)

    def emit(self, value: str | bytes) -> None:
        self.data.extend(bytes.fromhex(value) if isinstance(value, str) else value)

    def label(self, name: str) -> None:
        self.labels[name] = self.current_va

    def rel32(self, opcode: str, target: int | str) -> None:
        self.emit(opcode)
        self.fixups.append((len(self.data), target))
        self.data.extend(b"\0" * 4)

    def finish(self) -> bytes:
        for offset, target in self.fixups:
            destination = self.labels[target] if isinstance(target, str) else target
            struct.pack_into("<i", self.data, offset, destination - (self.va + offset + 4))
        return bytes(self.data)


def parse_headers(data: bytes | bytearray) -> dict:
    if data[:2] != b"MZ":
        raise ValueError("Not an MZ image")
    pe = u32(data, 0x3C)
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Not a PE image")
    optional = pe + 24
    if u16(data, optional) != 0x10B:
        raise ValueError("Expected a PE32 image")
    sections_offset = optional + u16(data, pe + 20)
    sections = []
    for index in range(u16(data, pe + 6)):
        offset = sections_offset + index * 40
        sections.append({
            "offset": offset,
            "name": bytes(data[offset:offset + 8]).rstrip(b"\0").decode("ascii"),
            "virtual_size": u32(data, offset + 8),
            "virtual_address": u32(data, offset + 12),
            "raw_size": u32(data, offset + 16),
            "raw_offset": u32(data, offset + 20),
            "characteristics": u32(data, offset + 36),
        })
    return {"pe": pe, "optional": optional, "sections_offset": sections_offset, "sections": sections}


def rva_to_offset(headers: dict, rva: int) -> int:
    for section in headers["sections"]:
        start = section["virtual_address"]
        span = max(section["virtual_size"], section["raw_size"])
        if start <= rva < start + span:
            if rva - start >= section["raw_size"]:
                raise ValueError(f"RVA 0x{rva:x} is not file-backed")
            return section["raw_offset"] + rva - start
    raise ValueError(f"RVA 0x{rva:x} is outside all sections")


def va_to_offset(headers: dict, va: int) -> int:
    return rva_to_offset(headers, va - IMAGE_BASE)


def neutralize_relocation(data: bytearray, headers: dict, target_rva: int) -> dict:
    optional = headers["optional"]
    directory = optional + 96 + 5 * 8
    reloc_rva = u32(data, directory)
    reloc_size = u32(data, directory + 4)
    cursor = rva_to_offset(headers, reloc_rva)
    end = cursor + reloc_size
    matches = []
    while cursor + 8 <= end:
        page = u32(data, cursor)
        block_size = u32(data, cursor + 4)
        if not page or block_size < 8 or cursor + block_size > end:
            break
        for entry_offset in range(cursor + 8, cursor + block_size, 2):
            entry = u16(data, entry_offset)
            if page + (entry & 0x0FFF) == target_rva and entry >> 12 == 3:
                matches.append((entry_offset, entry))
        cursor += block_size
    if len(matches) != 1:
        raise ValueError(f"Expected one HIGHLOW relocation for RVA 0x{target_rva:x}, found {len(matches)}")
    entry_offset, before = matches[0]
    after = before & 0x0FFF
    p16(data, entry_offset, after)
    return {
        "rva": f"0x{target_rva:08x}",
        "offset": entry_offset,
        "before": struct.pack("<H", before).hex(),
        "after": struct.pack("<H", after).hex(),
    }


def pe_checksum(data: bytes | bytearray, checksum_offset: int) -> int:
    image = bytearray(data)
    image[checksum_offset:checksum_offset + 4] = b"\0\0\0\0"
    total = 0
    for offset in range(0, len(image) - 1, 2):
        total += image[offset] | (image[offset + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    if len(image) & 1:
        total += image[-1]
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + len(image)) & 0xFFFFFFFF


def detour(source_va: int, target_va: int, size: int) -> bytes:
    if size < 5:
        raise ValueError("A near detour needs at least five bytes")
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5)) + b"\x90" * (size - 5)
