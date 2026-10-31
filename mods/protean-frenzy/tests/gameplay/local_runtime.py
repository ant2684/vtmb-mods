import json,sys,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
CONFIG=json.loads(Path(os.environ['PFI_CONFIG']).read_text())
def path(key):return Path(CONFIG[key])
COMMON=HERE/'_support'
sys.path[:0]=[str(COMMON),str(path('native_dependencies'))]
