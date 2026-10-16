"""Use the shared finalizer before any binary verification."""
from pathlib import Path
root=next(p for p in Path(__file__).resolve().parents if (p/'infra/common').is_dir())
source=root/'infra/common/finalize_pe.py'
exec(compile(source.read_bytes(),str(source),'exec'),globals())
