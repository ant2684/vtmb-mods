"""Remove LLD's optional zero-payload REPRO section before final verification.

Zig's stripped MinGW link still emits a type-16 debug directory in .buildid.
This bounded finalization preserves every other section's RVA and content.
It refuses symbols, signatures, other debug entries or unexpected layout.
"""
import argparse
import struct
from pathlib import Path
import pefile

def finalize(path):
    path = Path(path)
    raw = path.read_bytes()
    pe = pefile.PE(data=raw)
    assert pe.FILE_HEADER.Machine == 0x14c
    assert pe.FILE_HEADER.NumberOfSymbols == 0 and pe.FILE_HEADER.PointerToSymbolTable == 0
    assert not pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size, "signed image cannot be finalized"
    entries = getattr(pe, "DIRECTORY_ENTRY_DEBUG", [])
    if not entries:
        return
    assert all(d.struct.Type == 16 and d.struct.SizeOfData == 0 and d.struct.PointerToRawData == 0 for d in entries)
    sections = pe.sections
    removed = [s for s in sections if s.Name.rstrip(b"\0") == b".buildid"]
    assert len(removed) == 1
    section = removed[0]
    assert not section.Characteristics & 0x20000000
    dd = pe.OPTIONAL_HEADER.DATA_DIRECTORY[6]
    assert section.VirtualAddress <= dd.VirtualAddress and dd.VirtualAddress + dd.Size <= section.VirtualAddress + section.Misc_VirtualSize
    start, size = section.PointerToRawData, section.SizeOfRawData
    assert size > 0 and start + size <= len(raw)
    assert pe.get_overlay_data_start_offset() is None, "unexpected overlay"
    keep = [s for s in sections if s is not section]
    index = sections.index(section)
    assert index > 0
    preceding = sections[index-1]
    assert preceding.Name.rstrip(b"\0") == b".rdata" and not preceding.Characteristics & 0x20000000
    alignment = pe.OPTIONAL_HEADER.SectionAlignment
    assert (preceding.VirtualAddress + preceding.Misc_VirtualSize + alignment - 1) // alignment * alignment == section.VirtualAddress
    # Windows requires consecutive aligned virtual section extents. Cover the
    # removed page as zero-filled .rdata padding, preserving all other RVAs.
    preceding_size = section.VirtualAddress + section.Misc_VirtualSize - preceding.VirtualAddress
    original = {s.Name: (s.VirtualAddress, s.get_data()) for s in keep}
    data = bytearray(raw[:start] + raw[start + size:])
    struct.pack_into("<H", data, pe.FILE_HEADER.get_field_absolute_offset("NumberOfSections"), len(keep))
    struct.pack_into("<I", data, pe.FILE_HEADER.get_field_absolute_offset("TimeDateStamp"), 0)
    struct.pack_into("<II", data, dd.get_file_offset(), 0, 0)
    struct.pack_into("<I", data, pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfInitializedData"), pe.OPTIONAL_HEADER.SizeOfInitializedData - size)
    table = sections[0].get_file_offset()
    for i, s in enumerate(keep):
        header = bytearray(raw[s.get_file_offset():s.get_file_offset() + 40])
        if s is preceding:
            struct.pack_into("<I", header, 8, preceding_size)
        assert not s.PointerToRelocations and not s.PointerToLinenumbers
        if s.PointerToRawData >= start + size:
            struct.pack_into("<I", header, 20, s.PointerToRawData - size)
        else:
            assert s.PointerToRawData + s.SizeOfRawData <= start
        data[table + 40*i:table + 40*(i+1)] = header
    data[table + 40*len(keep):table + 40*len(sections)] = bytes(40)
    struct.pack_into("<I", data, pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum"), 0)
    cleaned = pefile.PE(data=bytes(data))
    assert not cleaned.OPTIONAL_HEADER.DATA_DIRECTORY[6].Size
    assert {s.Name: (s.VirtualAddress, s.get_data()) for s in cleaned.sections} == original
    struct.pack_into("<I", data, cleaned.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum"), cleaned.generate_checksum())
    path.write_bytes(data)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin")
    args = ap.parse_args()
    finalize(args.plugin)
    print("Finalized clean PE:", args.plugin)
