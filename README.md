# VTMB mods and regression tests

Source and tests for Console Pause, Protean Improved Core and its two model
alternatives, Frenzy Fixes, Subtitle Pause, Cutscene Subtitle Background and
History Stat Reset. Current release archives remain frozen. History 1.5.2
restores the native creation category pool after gender/History resets,
including Auto-Spend Points; its exact clean binary and distinct workflows
were verified and the user accepted the correction.

On Windows, install Python 3.12.10 and run `./Setup.ps1`. It creates the
ignored local environment and creates local.json only when absent. Configure
its local paths; RunTests.ps1 uses that environment and configuration by default:

```powershell
./RunTests.ps1 -Suite ci -Config ./local.json
./RunTests.ps1 -Suite offline -Config ./local.json
./RunTests.ps1 -Suite gameplay -Mod console -Scenario console.immediate -Config ./local.json
./RunTests.ps1 -Suite gameplay -List
```

The default suite is `offline`. `ci` builds our source and uses synthetic
fixtures without game files. `offline` additionally checks the exact frozen
archives, native game modules and models supplied locally. Gameplay runs are
sequential, opt-in and require nominated saves and a native collector. Missing
mandatory input produces `BLOCKED` and a nonzero exit code. JSON reports include
the first result, identities, scope and durations; they are stored under
`.local/results`.

For a new native candidate, use `-Mod <mod> -Candidate <final.vtm>` with
`offline`. The finalized candidate must match a pinned build of this checkout;
exact-binary harnesses then inspect its relocated code. Candidate mode also
propagates through gameplay preparation, installation and evidence when that
scenario has an inspected collector. An old release hash or
historical certificate is never accepted as evidence for it.

See [review](docs/review.md), [lessons](docs/lessons.md),
[gameplay and recovery](docs/gameplay.md) and [test catalog](docs/tests.md).
Historical recipes in individual `mods` directories are retained for provenance
and diagnostics; they are not safe substitutes for the new transaction runner.

Export a self-contained source capsule with
`python -m infra.export_capsule --mod console --output .local/console-source.zip`.
It contains one README and all required shared source dependencies. Existing
accepted source capsules are not repackaged. Game assets, personal saves,
private evidence, compiled helpers and rollback backups stay local.

The review found three failing OS cache-flush refusal paths. Reproduce them
with `./RunTests.ps1 -Suite faults -Config local.json`; their failure is not
hidden by passing retained CI/offline checks. Fresh gameplay adapters remain
incomplete; see docs/review.md for the exact unfinished scope.
