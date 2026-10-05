"""Build four-hit side chains from the exact accepted Claws 1.2.0 resources.

Standard-library-only, deterministic, no game installation writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

SIZE = 764
POINTERS = (0, 4, 24, 568, 664, 668, 704, 712)
COMBAT = (740, 744, 748)
HEADER_FIELDS = (0x8C, 0x110, 0x114)
ACCEPTED = {
    'Default Block': '5539EFCCAAA5B85E1FD82DAC2BD730486669B1D82E39017C31526232A4890641',
    'Fists Block': '7FCFDBEAFB480CADA5B85C74FAA4762F186FB3BDF428AC78B1A62877AFF83C3C',
    'Tire Iron Block': 'C5B5EA092E13BE72A55A4F383A80F076172DB9925A47D79D26E5FA8062948129',
}
DONORS = {
    'claws_pi_left3': 'claws_attack_far_left',
    'claws_pi_left4': 'claws_attack_med_right',
    'claws_pi_right3': 'claws_attack_far',
    'claws_pi_right4': 'claws_attack_med',
}
NEXT = {
    'claws_attack_far': 'claws_pi_left3',
    'claws_attack_far_left': 'claws_pi_right3',
    'claws_pi_left3': 'claws_pi_left4',
    'claws_pi_left4': None,
    'claws_pi_right3': 'claws_pi_right4',
    'claws_pi_right4': None,
}
CHAINS = {
    'left': ('claws_attack_med', 'claws_attack_far', 'claws_pi_left3', 'claws_pi_left4'),
    'right': ('claws_attack_med_right', 'claws_attack_far_left', 'claws_pi_right3', 'claws_pi_right4'),
}

def digest(data):
    return hashlib.sha256(data).hexdigest().upper()

def integer(data, offset):
    return struct.unpack_from('<i', data, offset)[0]

def put(data, offset, value):
    struct.pack_into('<i', data, offset, value)

def string(data, offset):
    if not 0 <= offset < len(data):
        raise ValueError('String outside model')
    end = data.find(b'\0', offset)
    if end < 0:
        raise ValueError('Unterminated string')
    return bytes(data[offset:end])

def validate(data):
    if data[:4] != b'IDST' or integer(data, 4) != 2531:
        raise ValueError('Expected a Bloodlines v2531 MDL')
    if integer(data, 0x8C) != len(data):
        raise ValueError('Wrong declared model size')
    count, table = integer(data, 0x110), integer(data, 0x114)
    if not 0 < count <= 500 or not 424 <= table <= len(data) - count * SIZE:
        raise ValueError('Invalid sequence table')

def sequences(data):
    validate(data)
    count, table = integer(data, 0x110), integer(data, 0x114)
    result = {}
    for index in range(count):
        pos = table + index * SIZE
        name = string(data, pos + integer(data, pos)).decode('ascii')
        if name in result:
            raise ValueError('Duplicate sequence label: ' + name)
        result[name] = pos
    return result

def combat_string(data, pos, field):
    value = integer(data, pos + field)
    if value < 0:
        if value != -1:
            raise ValueError('Unexpected negative combat sentinel')
        return None
    if value == 0:
        raise ValueError('Zero combat string offset')
    return string(data, pos + value)

def build_model(original):
    old = sequences(original)
    for name in set(DONORS.values()) | {'claws_attack_heavy'}:
        if name not in old:
            raise ValueError('Missing donor: ' + name)
    if any(name in old for name in DONORS):
        raise ValueError('Already contains new combo stages')
    for first, second, *_ in CHAINS.values():
        if combat_string(original, old[first], 744) != second.encode():
            raise ValueError('Unexpected first-hit chain')
        if combat_string(original, old[second], 744) != b'claws_attack_heavy':
            raise ValueError('Unexpected second-hit chain')

    names = list(old) + list(DONORS)
    table = (len(original) + 15) & ~15
    strings_start = table + len(names) * SIZE
    pool = bytearray()
    locations = {}

    def intern(value):
        if value not in locations:
            locations[value] = strings_start + len(pool)
            pool.extend(value + b'\0')
        return locations[value]

    records = bytearray()
    for index, name in enumerate(names):
        alias = name in DONORS
        donor = DONORS.get(name, name)
        before, after = old[donor], table + index * SIZE
        record = bytearray(original[before:before + SIZE])
        for field in POINTERS:
            value = integer(original, before + field)
            if value:
                target = before + value
                if not 0 <= target < len(original):
                    raise ValueError(f'Invalid relative pointer in {donor} at {field}')
                put(record, field, target - after)
        for field in COMBAT:
            value = combat_string(original, before, field)
            if field == 744 and name in NEXT:
                value = None if NEXT[name] is None else NEXT[name].encode('ascii')
            if value is None:
                put(record, field, -1)
            else:
                relative = intern(value) - after
                if not 0 < relative < 2**31:
                    raise ValueError('Combat string must follow the new table')
                put(record, field, relative)
        if alias:
            put(record, 0, intern(name.encode('ascii')) - after)
            # Unnamed activity, ACT_INVALID, zero selection weight: lookup by
            # nextattack label works, activity-based first-hit selection cannot.
            put(record, 4, intern(b'') - after)
            put(record, 12, -1)
            put(record, 16, 0)
        records.extend(record)

    result = bytearray(original)
    result.extend(b'\0' * (table - len(result)))
    result.extend(records)
    result.extend(pool)
    result.extend(b'\0' * ((-len(result)) % 16))
    put(result, 0x8C, len(result))
    put(result, 0x110, len(names))
    put(result, 0x114, table)
    verify_model(original, result)
    return bytes(result)

def verify_model(original, patched):
    """Compare bytes, pointer targets, scalar metadata and complete graph."""
    old, new = sequences(original), sequences(patched)
    if list(new) != list(old) + list(DONORS):
        raise AssertionError('Unexpected labels or original sequence order')
    allowed_header = {i for field in HEADER_FIELDS for i in range(field, field + 4)}
    if any(a != b and i not in allowed_header
           for i, (a, b) in enumerate(zip(original, patched[:len(original)]))):
        raise AssertionError('Original resource body changed')

    for name, after in new.items():
        alias = name in DONORS
        donor = DONORS.get(name, name)
        before = old[donor]
        allowed = {i for field in POINTERS + COMBAT for i in range(field, field + 4)}
        if alias:
            allowed.update(range(12, 20))
        for i in range(SIZE):
            if i not in allowed and original[before + i] != patched[after + i]:
                raise AssertionError(f'Changed metadata in {name} at {i}')
        for field in POINTERS:
            x, y = integer(original, before + field), integer(patched, after + field)
            if alias and field in (0, 4):
                wanted = name.encode() if field == 0 else b''
                if string(patched, after + y) != wanted:
                    raise AssertionError('Wrong alias name/activity')
            elif (x == 0 and y != 0) or (x != 0 and before + x != after + y):
                raise AssertionError(f'Pointer target changed: {name} field {field}')
        for field in COMBAT:
            wanted = combat_string(original, before, field)
            if field == 744 and name in NEXT:
                wanted = None if NEXT[name] is None else NEXT[name].encode()
            if combat_string(patched, after, field) != wanted:
                raise AssertionError(f'Combat link changed: {name} field {field}')
        if alias and (integer(patched, after + 12), integer(patched, after + 16)) != (-1, 0):
            raise AssertionError('Alias is eligible for activity selection')

    for expected in CHAINS.values():
        actual, name = [], expected[0]
        while name is not None:
            if name in actual or name not in new:
                raise AssertionError('Cycle or missing sequence in side combo')
            actual.append(name)
            value = combat_string(patched, new[name], 744)
            name = None if value is None else value.decode('ascii')
        if tuple(actual) != expected:
            raise AssertionError('Wrong combo chain')

def payloads(archive, expected_hash):
    raw = archive.read_bytes()
    if digest(raw) != expected_hash:
        raise ValueError('Unknown accepted archive: ' + str(archive))
    with zipfile.ZipFile(archive) as z:
        items = {info.filename: z.read(info) for info in z.infolist() if info.filename.endswith('.mdl')}
        if len(items) not in (2, 4):
            raise ValueError('Unexpected gameplay resource count')
    return items

def readme(edition):
    return f'''Protean Improved - Four-hit side combos - {edition}
====================================================

Replaces the heavy third hit of the left and right Claws side combos with
two existing fast attacks. Each chain ends after four hits. Each follow-up
uses normal attack input. The accepted Claws reach and forward movement
improvements are retained. This edition uses {edition.lower()}.

Install only one blocking edition. Exit the game. Back up every existing
destination file outside the game directory before replacing it. Copy the
Unofficial_Patch folder into the Bloodlines directory containing Vampire.exe.
Do not mix claws.mdl files from different editions.

Verify left and right side combos with Protean Claws and Tiger's Claws.
Check alternating hands, four stages, a normal end, hits after knockback,
interruptions and blocking with male and female characters.

Rollback: exit the game and restore your backed-up files. If a destination
file did not exist before installation, remove only that installed file to
return to the game's packed resource. Restore all files of the edition together.
'''

def build_packages(releases, output):
    if output.exists():
        raise ValueError('Output already exists; use a fresh task directory')
    # Validate all inputs and build in memory before creating output files.
    builds = {}
    audit = {'status': 'unpublished, in-game acceptance pending', 'editions': {}}
    for edition, accepted_hash in ACCEPTED.items():
        archive = releases / f'VTMB Protean Claws Hit Fix 1.2.0 - {edition}.zip'
        baseline = payloads(archive, accepted_hash)
        result, identities = {}, {}
        for path, data in baseline.items():
            result[path] = build_model(data) if path.endswith('/claws.mdl') else data
            identities[path] = {'baseline_sha256': digest(data), 'candidate_sha256': digest(result[path]),
                                'baseline_size': len(data), 'candidate_size': len(result[path])}
        result['README.txt'] = readme(edition).encode('ascii')
        builds[edition] = result
        audit['editions'][edition] = identities
    output.mkdir(parents=True)
    for edition, files in builds.items():
        folder = output / edition
        for path, data in files.items():
            destination = folder / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        archive = output / f'Protean Improved - Four-hit Combos - {edition}.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for path, data in files.items():
                info = zipfile.ZipInfo(path, (2026, 9, 30, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        with zipfile.ZipFile(archive) as z:
            if set(z.namelist()) != set(files) or any(z.read(p) != data for p, data in files.items()):
                raise AssertionError('Archive round-trip verification failed')
        audit['editions'][edition]['archive_sha256'] = digest(archive.read_bytes())
    return audit

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--releases', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_packages(args.releases.resolve(), args.output.resolve()), indent=2))
