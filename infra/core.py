"""Explicit gates: unlike assert, these also run under python -O."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Failure(RuntimeError):
    pass


class Blocked(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Failure(message)


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def digest(path):
    return sha(Path(path).read_bytes())


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.pending')
    with tmp.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def catalog():
    path=ROOT / 'docs/release_catalog.json'
    if path.exists():return read_json(path)
    from infra.release_data import DATA
    return DATA


def need(config, key):
    value = config.get(key)
    if not value or 'REQUIRED' in str(value):
        raise Blocked('Configure local input: ' + key)
    return value


def run(command, timeout=180, env=None, cwd=None, process_tree=False):
    merged = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONOPTIMIZE='0')
    if env:
        merged.update(env)
    try:
        if process_tree:
            from infra.job_process import run as run_tree
            p = run_tree([str(a) for a in command], cwd=cwd, env=merged, timeout=timeout)
        else:
            p = subprocess.run([str(a) for a in command], cwd=cwd, env=merged,
                               capture_output=True, text=True, timeout=timeout,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except FileNotFoundError as e:
        raise Blocked('Executable missing: ' + str(command[0])) from e
    except subprocess.TimeoutExpired as e:
        def text(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
        stdout, stderr = text(e.output), text(e.stderr)
        error = Blocked('Preparation or verifier timeout; no behavioral PASS: ' + str(command[0])
                        + '\nFirst stdout:\n' + stdout + '\nFirst stderr:\n' + stderr)
        error.stdout, error.stderr, error.timeout_seconds = stdout, stderr, timeout
        raise error from e
    require(p.returncode == 0, 'Command failed: ' + ' '.join(map(str, command)) + '\n' + p.stdout + '\n' + p.stderr)
    return p.stdout + p.stderr
