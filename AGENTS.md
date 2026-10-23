# VTMB public source repository

Read README.md and docs/PUBLICATION_POLICY.md before changing this repository.
The owner's private workbench is the primary location for ongoing implementation,
prototype source, findings, exact artifact identities and continuation notes.
This repository receives only selected original source, generators, tests and public
documentation after an explicit owner request to publish here. Do not mirror or merge
private workbench history. A normal development/private-save request is not public
publication authorization. Ask only if the requested public scope cannot be resolved.

Never export personal journals/settings/path maps, game binaries or resources, saves,
captures, backups, transfer ZIPs, caches or diagnostic residue. Keep incomplete local
work private unless its publication is specifically requested. Preserve provenance,
supported input identities and test limitations. Technical PASS, user acceptance,
packaging and external publication are distinct events.

Make one task-focused commit after required checks. Inspect staged blobs with
python -B -m infra.public_tree --tracked and review the exact diff before pushing.
Push only the explicitly authorized scope; do not change visibility or frozen release
bytes/versions as a side effect. Report commit, push and validation results.

Prefer scripts/direct APIs for tests and retain useful regression checks with source.
Final runtime tests use exact clean delivery bytes; never strip/rebuild afterward.
Preserve game files, personal saves/config, display mode/resolution and original
timestamps. Control only a game process created by the test. Tests must exercise
distinct required workflows rather than arbitrary exhaustive parameter combinations.
