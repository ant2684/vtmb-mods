# Adding a future mod

Keep related mods in this repository so a common runner, recovery protocol and
CI have one implementation. Use a separate repository only for a different
ownership/license boundary or an independently maintained project. Game data
and private evidence remain local in either case.

Start with a requirement and transition table using the format in lessons.md.
Each scenario needs a stable ID/version, platform, mandatory inputs, finite
preparation/execution timeout, native observed before/after states, expected
behavior and a preserved first result. Document why any extra clan/model/sex
combination exercises a different path. A missing collector is BLOCKED.

Place original source, generated helpers/generators and tests in `mods/<id>`.
Reuse `infra/common` through source adapters. Add provenance/license origins
before publishing; do not copy a complete game image, map, model, recording,
save, private log or binary fixture into Git. Add public instructions explaining
required local inputs rather than redistributing those inputs.

Register the family and frozen archives in release_catalog.json only after
finalization. Bind every payload/source member, exports and supported module
identity. For a pre-release candidate use its matching source checkout and
exact finalized PE. Add its own exact verifier to native.py, with source/PE
alignment and relocated machine-code/ABI tests; never fall through another
family's verifier. Extend runner.py with named CI/offline/gameplay scenarios.
The runner dispatch for a future family must return BLOCKED until its verifier
is implemented; compilation alone is not behavioral acceptance.

CI uses only our source and licensed synthetic fixtures. Add refusal, occupied
site, partial install, rollback and persistent OS failure cases with helper
lifetime/protection checks. Local offline tests use exact supported native
fixtures. Gameplay collection uses the shared transaction, inspected native
observations and an independent requirement-specific audit. Mark any remaining
gameplay gap explicitly and give its reproduction command.

Test exact finalized payload bytes; retain failure evidence outside delivery.
Export and independently test a capsule with `infra.export_capsule` and
`infra.export_validation`. Gameplay ZIP has only required game-layout files
and one English manual README.txt; source ZIP has one README.md and source
verification tools. Do not rebuild or strip tested bytes afterward.

Commit source and tests with their origin and validation record in the same
change. A behavior fix should be a separate reviewable commit/PR with candidate
identity and relevant fresh results, rather than an unexplained side effect of
moving tests. Passing CI never removes a recorded release fault or a missing
gameplay certificate.
