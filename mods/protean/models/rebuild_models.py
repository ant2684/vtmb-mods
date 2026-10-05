"""Rebuild and verify four-hit models using only current release archives."""
from __future__ import annotations
import argparse
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'reference'))
from combo_models import build_model, digest, verify_model
from verify_packages import engine_chains

VERSION = '1.2.1'
EDITIONS = ('Default Block', 'Fists Block', 'Tire Iron Block')
BASELINES = {
    ('Default Block', 'female'): 'FC24EFC22892DC91ABE21FF029C3847AA082FB0D182D4FABFC0830EFAD555381',
    ('Default Block', 'male'): '09447AB4774E2FDAB9ADFD7FF0A5BEF03703CBA18452DD3F01F15E0FD1123A7B',
    ('Fists Block', 'female'): 'DBB952F77BD4A7F001A1BC4FDB45EE7C68470F9FA5501277521525C68FE43217',
    ('Fists Block', 'male'): '58D76A3462DEF42841E5D3E5BFD4327733CEB1069499DF637CBF1B654A591A96',
}
FINALS = {
    ('Default Block', 'female'): 'FB5138B57776CAAFBD8440B4662ADABDF8AE6337CB8F191E8E83F651E54C85F7',
    ('Default Block', 'male'): 'CF7B8FEDDF04150CA4DA32421333969545186F6FE002BADC8366AFFAA3DF3EC6',
    ('Fists Block', 'female'): '1F412BE922BD392C2C1BA72A6CE1CC1BFFEE22ED5193FDF91C85E55A10A2CD32',
    ('Fists Block', 'male'): '94AB12A98F366914066F588CC936DBB961139EB2A7D960FF19A5D824DEC61CF9',
}
DONORS = {
    ('Fists Block', 'female'): 'A828D4532633100F3BB1429E8DCD1B74AD171FB65A58EDFC54A75C85F112DCF5',
    ('Fists Block', 'male'): '58FA4A62E0F324A60F559428C286FB8A93E94157F3F16E283384B2A4A54EED8B',
    ('Tire Iron Block', 'female'): '094405697BA09B3CABC93DC6C4E6A6FE3ABDF26DF0B2CD26FF69F87FD3A3CC49',
    ('Tire Iron Block', 'male'): '64987559A64F99A1B106E50039DF06C6416C86432021B6383448B575040A0235',
}

def archive_name(edition):
    return f'VTMB Protean Improved {VERSION} - Four-hit Combos - {edition}.zip'

def model_key(edition, sex):
    return ('Fists Block' if edition == 'Tire Iron Block' else edition, sex)

def baseline(candidate, edition, sex):
    key = model_key(edition, sex)
    if digest(candidate) != FINALS[key]:
        raise ValueError('Unknown release model')
    size, table = (753552, 631012) if sex == 'female' else (745936, 623444)
    original = bytearray(candidate[:size])
    for offset, value in ((0x8c, size), (0x110, 42), (0x114, table)):
        struct.pack_into('<i', original, offset, value)
    if digest(original) != BASELINES[key]:
        raise AssertionError('Recovered baseline identity mismatch')
    return bytes(original)

def readme(edition):
    return f'''VTMB Protean Improved {VERSION} - Four-hit Combos - {edition}

Four-hit variation of the Claws reach and forward-movement improvements.
Protean Claws and Tiger's Claws side combos use the existing fast movements:
left: L1 -> L2 -> R2 -> R1; right: R1 -> R2 -> L2 -> L1.
Each follow-up requires normal attack input; each chain ends after hit four.
Other uses of the heavy attack remain available. Blocking: {edition.lower()}.

Requirements: 32-bit Bloodlines with the recorded Unofficial Patch 11.5
game-directory layout. Other model replacements require a compatibility review.
Core is a separate optional package. Install only one Claws blocking edition.

Install
1. Exit the game. Back up every existing destination file outside the game
   directory before replacing it, recording which files did not exist.
2. Copy this archive's Unofficial_Patch folder into the Bloodlines directory
   containing Vampire.exe. Keep both sexes and all donor models together.
3. Launch the Unofficial_Patch profile. Do not mix different blocking editions.

Rollback
Exit the game and restore all backed-up destination files together. Remove
only installed files that did not exist before installation, returning those
paths to the game's packed resources.
'''.encode('ascii')

def write_zip(path, files):
    if path.exists():
        raise ValueError('Refusing to overwrite: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, (2026, 9, 30, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    with zipfile.ZipFile(path) as z:
        if z.namelist() != list(files) or any(z.read(p) != d for p, d in files.items()):
            raise AssertionError('ZIP round-trip mismatch')

def read_inputs(releases, edition):
    paths = {f'Unofficial_Patch/models/character/shared/{sex}/claws.mdl'
             for sex in ('female', 'male')}
    if edition != 'Default Block':
        donor = 'fists' if edition == 'Fists Block' else 'tireiron'
        paths.update(f'Unofficial_Patch/models/character/shared/{sex}/{donor}.mdl'
                     for sex in ('female', 'male'))
    paths.add('README.txt')
    with zipfile.ZipFile(releases / archive_name(edition)) as z:
        if len(z.namelist()) != len(paths) or set(z.namelist()) != paths:
            raise ValueError('Release ZIP path allowlist mismatch')
        files = {p: z.read(p) for p in z.namelist()}
    if files['README.txt'] != readme(edition):
        raise ValueError('Unexpected release instructions')
    for p, data in files.items():
        if p.endswith('.mdl'):
            sex = p.split('/')[-2]
            if p.endswith('/claws.mdl'):
                original = baseline(data, edition, sex)
                verify_model(original, data)
                engine_chains(data)
                if build_model(original) != data:
                    raise AssertionError('Model rebuild is not byte-identical')
            elif digest(data) != DONORS[edition, sex]:
                raise ValueError('Blocking donor identity mismatch')
    # Extract into an empty directory and compare every resource byte.
    with tempfile.TemporaryDirectory(prefix='protean-release-verify-') as tmp:
        root = Path(tmp).resolve()
        for p, data in files.items():
            target = (root / p).resolve()
            if not target.is_relative_to(root):
                raise ValueError('Unsafe archive path')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if target.read_bytes() != data:
                raise AssertionError('Extracted bytes differ')
    return files

def rebuild(releases, output):
    if output.exists():
        raise ValueError('Output directory must not exist')
    builds = {}
    for edition in EDITIONS:
        files = read_inputs(releases, edition)
        for p in files:
            if p.endswith('/claws.mdl'):
                files[p] = build_model(baseline(files[p], edition, p.split('/')[-2]))
        builds[edition] = files
    output.mkdir(parents=True)
    for edition, files in builds.items():
        write_zip(output / archive_name(edition), files)
        if (output / archive_name(edition)).read_bytes() != (releases / archive_name(edition)).read_bytes():
            raise AssertionError('Release ZIP is not byte-identical')
        print(edition + ': extraction, baseline recovery, graph, preservation and exact ZIP rebuild PASS')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--releases', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        rebuild(args.releases.resolve(), args.output.resolve())
    else:
        for edition in EDITIONS:
            read_inputs(args.releases.resolve(), edition)
            print(edition + ': verification PASS')
