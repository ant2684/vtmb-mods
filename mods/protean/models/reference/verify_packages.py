"""Extract packages into empty temporary directories and validate payloads."""
import argparse
import struct
import tempfile
import zipfile
from pathlib import Path
from combo_models import ACCEPTED, CHAINS, DONORS, payloads, verify_model

def engine_chains(data):
    # Independent reading of descriptor labels and signed nextattack fields.
    count, table = struct.unpack_from('<ii', data, 0x110)
    nodes = {}
    for index in range(count):
        pos = table + index * 764
        name_at = pos + struct.unpack_from('<i', data, pos)[0]
        name = data[name_at:data.index(0, name_at)].decode('ascii')
        relative = struct.unpack_from('<i', data, pos + 744)[0]
        target = None
        if relative >= 0:
            at = pos + relative
            target = data[at:data.index(0, at)].decode('ascii')
        nodes[name] = target
    for wanted in CHAINS.values():
        actual = []
        node = wanted[0]
        while node is not None:
            if node in actual or len(actual) >= 4:
                raise AssertionError('Combo cycle or more than four hits')
            actual.append(node)
            node = nodes[node]
        if tuple(actual) != wanted:
            raise AssertionError('Engine-visible chain is incomplete')

def verify(releases, packages):
    for edition, expected_hash in ACCEPTED.items():
        baseline = payloads(releases / f'VTMB Protean Claws Hit Fix 1.2.0 - {edition}.zip', expected_hash)
        expected_paths = set(baseline) | {'README.txt'}
        archive = packages / f'Protean Improved - Four-hit Combos - {edition}.zip'
        with tempfile.TemporaryDirectory(prefix='protean-combo-verify-') as tmp:
            root = Path(tmp).resolve()
            with zipfile.ZipFile(archive) as z:
                if len(z.namelist()) != len(expected_paths) or set(z.namelist()) != expected_paths:
                    raise AssertionError('ZIP path allowlist mismatch')
                for path in z.namelist():
                    destination = (root / path).resolve()
                    if not destination.is_relative_to(root):
                        raise AssertionError('Unsafe archive path')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(z.read(path))
            for path, original in baseline.items():
                candidate = (root / path).read_bytes()
                if candidate != (packages / edition / path).read_bytes():
                    raise AssertionError('Loose payload differs from archive')
                if path.endswith('/claws.mdl'):
                    verify_model(original, candidate)
                    engine_chains(candidate)
                elif candidate != original:
                    raise AssertionError('Blocking donor changed')
            readme = (root / 'README.txt').read_text('ascii')
            if not all(word in readme for word in ('Back up', 'Verify', 'Rollback')):
                raise AssertionError('Missing manual installation/verification/rollback')
        print(edition + ': archive allowlist, extraction, bytes, four-hit graph and donor preservation PASS')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--releases', required=True, type=Path)
    parser.add_argument('--packages', required=True, type=Path)
    args = parser.parse_args()
    verify(args.releases.resolve(), args.packages.resolve())
