"""Fail closed on diagnostic remnants in a final plugin or gameplay payload."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import pefile

def verify_clean(plugin, exports, source=None, payload=None):
    plugin = Path(plugin)
    raw = plugin.read_bytes()
    pe = pefile.PE(data=raw)
    assert pe.FILE_HEADER.Machine == 0x14c and pe.OPTIONAL_HEADER.Magic == 0x10b
    actual = {s.name.decode() for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
    assert actual == set(exports), ("unexpected exports", actual)
    assert not pe.OPTIONAL_HEADER.DATA_DIRECTORY[6].Size, "PE debug directory remains"
    assert pe.FILE_HEADER.NumberOfSymbols == 0, "COFF symbols remain"
    for section in pe.sections:
        name = section.Name.rstrip(b"\0").decode("ascii", "replace").lower()
        assert not name.startswith((".debug", ".zdebug")), ("debug section", name)
        # Long section names require a COFF string table; clean builds need none.
        assert not name.startswith("/"), ("unstripped long section name", name)
    imports = {s.name.decode() for d in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []) for s in d.imports if s.name}
    assert not imports.intersection({"CreateFileA", "CreateFileW", "WriteFile", "fopen", "fprintf", "OutputDebugStringA", "OutputDebugStringW", "MessageBoxA", "MessageBoxW", "CreateProcessA", "CreateProcessW", "SendInput"}), imports
    for value in re.findall(rb"[\x20-\x7e]{6,}", raw):
        lower = value.lower()
        assert b".pdb" not in lower and b".log" not in lower, ("diagnostic filename", value)
        assert not any(t in lower for t in (b"radio stream activation:", b"radio on:", b"radio loop:", b"subtitle pause fix:", b"cutscene subtitle background fix:", b"remaining silent.", b"unsupported or occupied subtitle/", b"install refused:")), ("diagnostic string", value)
    if source:
        for path in Path(source).glob("*.[ch]"):
            text = path.read_text()
            assert not re.search(r"\b(?:log_status|report|printf|fprintf|snprintf|fopen|CreateFile[AW]|WriteFile|OutputDebugString[AW])\s*\(", text), ("logging in native source", path)
    if payload:
        payload = Path(payload)
        actual_files = {p.relative_to(payload).as_posix() for p in payload.rglob("*") if p.is_file()}
        assert actual_files == {"README.txt", "Bin/loader/" + plugin.name}, ("unexpected payload files", actual_files)
        assert (payload / "Bin/loader" / plugin.name).read_bytes() == raw, "payload binary differs"
    return {"result": "PASS", "binary": str(plugin.resolve()), "sha256": hashlib.sha256(raw).hexdigest().upper(), "size": len(raw), "checks": ["exact loader exports", "no PE debug directory/symbols/debug sections", "no logging/diagnostic strings or file-write imports", "no native-source logging", "exact payload membership if supplied"]}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--exports", nargs="+", required=True)
    ap.add_argument("--source")
    ap.add_argument("--payload")
    ap.add_argument("--output")
    args = ap.parse_args()
    result = verify_clean(args.plugin, args.exports, args.source, args.payload)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
