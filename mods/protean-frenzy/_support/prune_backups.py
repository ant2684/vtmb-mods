"""Remove only backup/ trees belonging to completed, restored test sessions."""
import argparse, datetime, hashlib, json, shutil
from pathlib import Path

def prune(session):
    session = Path(session).resolve()
    backup = session / 'backup'
    if not backup.exists():
        return 0
    assert not backup.is_symlink() and backup.resolve().parent == session
    result = json.loads((session / 'result.json').read_text())
    restored = json.loads((session / 'restored.json').read_text())
    assert result.get('restored') and restored.get('restored'), session
    manifest = session / 'transaction.json'
    assert json.loads(manifest.read_text()).get('files'), session
    paths = list(backup.rglob('*'))
    assert not any(p.is_symlink() or p.is_junction() for p in paths), session
    files = [p for p in paths if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    receipt = dict(restored=True, removed_files=len(files), removed_bytes=size,
                   transaction_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                   utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   reason='Owner requested immediate deletion of redundant restored-session backups')
    # Exact absolute target checked above; never remove a session or evidence tree.
    shutil.rmtree(backup)
    assert not backup.exists()
    (session / 'backup-pruned.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return size

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('roots', nargs='+', type=Path)
    a = ap.parse_args()
    total = 0
    count = 0
    for root in a.roots:
        root = root.resolve(strict=True)
        for backup in sorted(root.glob('*/backup')):
            assert backup.resolve().is_relative_to(root)
            total += prune(backup.parent)
            count += 1
    print(json.dumps(dict(pruned_sessions=count, reclaimed_bytes=total)))
