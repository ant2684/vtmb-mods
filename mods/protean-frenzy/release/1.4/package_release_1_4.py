"""Compose the Protean & Frenzy Improved 1.4 game ZIP from qualified inputs."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PREVIOUS = "5b7bc18e461b64831c784022323316916029febd57e21cc5d5681b5992eb7169"
LOADER = "Bin/loader/"
PATCH = "Unofficial_Patch/"
CORE = LOADER + "protean-frenzy-improved.vtm"
INI = LOADER + "protean-frenzy-improved.ini"
ITEM = PATCH + "vdata/items/item_w_claws.txt"
CLAW_MODELS = {
    PATCH + f"models/character/shared/{sex}/claws.mdl" for sex in ("female", "male")
}
BASE_PAYLOAD = CLAW_MODELS | {
    CORE, INI, ITEM,
    PATCH + "maps/la_library_1.bsp",
    PATCH + "maps/sp_observatory_2.bsp",
    PATCH + "particles/stealth_claws_emitter.txt",
}
REPLACEMENTS = {
    ITEM: "8e2f8a295cb66509167070d8f6633f7d3af55626357f28d5202abfc90b0e5c07",
    PATCH + "sound/Weapons/Melee/Claws/pfi_claws_in.wav":
        "c79d6f6233602a7e7db570cf6f08e8454819989c1ff7a85fd601e962d50b4709",
    PATCH + "sound/Weapons/Melee/Claws/pfi_claws_out.wav":
        "7c8813970de1834e124785e497d8dc1ffd7aeebd7c22854a183fec26ac5e14c0",
}
MAIN_SHA = "8d9d069640e8e6c309e9b9a97852b3e8013143abadbc6305032d7cadc52f9f3b"
INI_SHA = "04494b83c61bd6bd59eb0a492e67e2c7d7ce80b1826bcbf90c0666b719031e82"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_names(names):
    casefolded = {name.casefold() for name in names}
    require(len(casefolded) == len(names), "Duplicate ZIP member")
    for name in names:
        path = PurePosixPath(name)
        require(
            path.as_posix() == name and not path.is_absolute() and '..' not in path.parts
            and re.fullmatch(r"[A-Za-z0-9_./& +()-]+", name), f"Unsafe name: {name}"
        )


def checked_read(root, name, expected):
    data = (root / name).read_bytes()
    require(digest(data) == expected, f"Input hash differs: {name}")
    return data


def hash_members(archive):
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
        verify_names(names)
        require(bundle.testzip() is None, "Invalid ZIP CRC")
        return {name: digest(bundle.read(name)) for name in names}


def write_zip(archive, members):
    verify_names(list(members))
    expected = {name: digest(data) for name, data in sorted(members.items())}
    with ZipFile(archive, "x") as bundle:
        for name in expected:
            member = ZipInfo(name, (2026, 11, 25, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            bundle.writestr(member, members[name], compress_type=ZIP_DEFLATED, compresslevel=6)
    require(hash_members(archive) == expected, "ZIP content differs from the input bytes")
    return expected


def compose(previous, assets, core, finisher, manual, archive):
    require(digest(previous.read_bytes()) == PREVIOUS, "Unexpected 1.3.2 archive")
    with ZipFile(previous) as baseline:
        require(baseline.testzip() is None, "Corrupt 1.3.2 archive")
        require(set(baseline.namelist()) == BASE_PAYLOAD | {"README.txt"}, "Unexpected baseline files")
        files = {name: baseline.read(name) for name in BASE_PAYLOAD}

    models = re.compile(re.escape(PATCH) + r"models/character/.+\.mdl\Z")
    particles = re.compile(re.escape(PATCH) + r"particles/pfi_[\w]+\.txt\Z")
    verify_names(list(finisher))
    require(len(finisher) == 234 and set(finisher) & BASE_PAYLOAD == CLAW_MODELS,
            "Unexpected finisher file count or overlap with the baseline")
    require(sum(bool(models.fullmatch(name)) for name in finisher) == 221 and
            sum(bool(particles.fullmatch(name)) for name in finisher) == 13,
            "Unexpected model or particle paths")
    for name, sha in (finisher | REPLACEMENTS).items():
        files[name] = checked_read(assets, name, sha)
    files[CORE] = checked_read(core, CORE, MAIN_SHA)
    files[INI] = checked_read(core, INI, INI_SHA)
    require(len(files) == 242, "Unexpected gameplay payload count")
    files["README.txt"] = manual.read_text(encoding="ascii").replace("\n", "\r\n").encode("ascii")
    return write_zip(archive, files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("previous", "assets", "core", "manual", "archive", "receipt"):
        parser.add_argument(arg, type=Path)
    parser.add_argument("--finisher-manifest", type=Path)
    args = parser.parse_args()
    if args.finisher_manifest:
        finisher = json.loads(args.finisher_manifest.read_text(encoding="utf-8"))["installed"]
    else:
        from finisher_inputs import FINISHER_INPUTS
        finisher = FINISHER_INPUTS
    members = compose(args.previous, args.assets, args.core, finisher, args.manual, args.archive)
    with args.receipt.open("x", encoding="utf-8") as receipt:
        json.dump({"version": "1.4", "archive_sha256": digest(args.archive.read_bytes()),
                   "members": members}, receipt, indent=2)
        receipt.write("\n")


if __name__ == "__main__":
    main()
