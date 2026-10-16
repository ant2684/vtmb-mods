"""Manual-only candidate delivery, gated by exact and fresh gameplay evidence."""
import argparse
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from infra.core import digest, read_json, require, sha
from infra.export_capsule import export
from infra.release import clean_pe, members
from mods.container.tests.audit import audit

MANUAL = """Container Stack Fix

Keeps stackable items visible in containers and vendor inventories when the
player already owns the same item. Native stack limits, transfers and prices
remain in effect. Give/Sell is disabled when the receiving stack is full and
becomes available after space is freed. Stacked purchases use the item price. Supports the original
Bloodlines client and server used by the
Unofficial Patch. An incompatible or already modified hook site is left alone.

Installation
Close the game. Back up any existing Bin\\loader\\container-stack-fix.vtm.
Copy the supplied Bin folder into the Bloodlines installation containing
Vampire.exe, merging the folders. The integrated Mod Loader loads the plugin
automatically. No game DLL or save file needs replacement.

Rollback
Close the game. Remove Bin\\loader\\container-stack-fix.vtm, or restore your
previous copy if one was backed up. The plugin only patches process memory;
existing saves remain usable.
"""


def package(plugin, certificate, observations, output):
    plugin, output = Path(plugin), Path(output)
    frozen = plugin.read_bytes()
    pin = sha(frozen)
    clean_pe(frozen, ['loaded_client','loaded_server'], 'container')
    technical = read_json(certificate)
    exact = [r for r in technical['results'] if r['id'] == 'container.exact']
    require(technical['status'] == 'PASS' and len(exact) == 1 and
            exact[0]['status'] == 'PASS' and exact[0]['observed']['sha256'] == pin,
            'Exact clean candidate certificate differs')
    observations = Path(observations)
    evidence = read_json(observations)
    require(evidence['scenario'] == 'container.stacks' and evidence['scenario_version'] >= 3 and
            evidence['artifacts'] == {'Bin/loader/container-stack-fix.vtm': pin},
            'Fresh gameplay used another candidate')
    audit(evidence)
    require(read_json(observations.parent / 'preservation-result.json')['status'] == 'PASS',
            'Temporary installation/settings have not been restored')
    output.mkdir(parents=True, exist_ok=True)
    payload = output / 'Container Stack Fix.zip'
    source = output / 'Container Stack Fix Source.zip'
    require(not payload.exists() and not source.exists(), 'Refuse delivery overwrite')
    files = {'Bin/loader/container-stack-fix.vtm': frozen,
             'README.txt': MANUAL.encode('ascii')}
    pending = payload.with_suffix('.zip.pending')
    require(not pending.exists(), 'Unfinished payload requires inspection')
    with zipfile.ZipFile(pending, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 10, 16, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(entry, data)
    require(members(pending) == files, 'Payload bytes/membership differ')
    source_result = export('container', source, plugin)
    require(members(source)['reference/container-stack-fix.vtm'] == files['Bin/loader/container-stack-fix.vtm'],
            'Source reference differs from tested gameplay')
    pending.replace(payload)
    return {'plugin_sha256': pin, 'payload_sha256': digest(payload),
            'source': source_result, 'files': sorted(files)}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--plugin', required=True)
    p.add_argument('--certificate', required=True)
    p.add_argument('--observations', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(json.dumps(package(a.plugin, a.certificate, a.observations, a.output), indent=2))
