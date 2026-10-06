"""Adapter to the shared, capsule-exported helper."""
from pathlib import Path as _Path
_root = next(p for p in _Path(__file__).resolve().parents if (p / "infra/common").is_dir())
_shared = _root / "infra/common/process_reader.py"
exec(compile(_shared.read_bytes(), str(_shared), "exec"), globals())