# Test catalog and reproducibility

Python 3.12.10, Zig 0.15.2 and the exact dependencies in requirements.txt are
pinned. Setup installs into ignored local directories. GitHub Actions uses
Windows hosted runners, commit-pinned Actions and read-only repository rights.
Public PRs never run against the owner's game or a self-hosted game machine.

`RunTests.ps1 -Suite <suite> -List` lists mandatory scenarios and finite
timeouts. `-Mod` selects one family. `-Scenario` selects one named check in any suite.
The JSON report records a unique session, scenario version, expected/observed
behavior, duration and input identity. `PASS`, `FAIL`, `BLOCKED` and `SKIPPED`
are reserved statuses; no selected required test is silently skipped. Missing
inputs and preparation timeouts are BLOCKED, proven violations are FAIL.

| Suite | Inputs | Checks |
| --- | --- | --- |
| ci | Our checkout, pinned Python/Zig/dependencies, Windows | Infrastructure rejection/recovery tests; all six clean builds, native Windows load with relocations and available synthetic harnesses |
| offline | CI inputs, exact current release directory and supported local game modules | All 18 archives, exact manifests/manuals, clean PE, BSP permission, exact native code/ABI/rollback, all model variants/corruptions/reconstruction |
| gameplay | Offline inputs, nominated scenario saves, inspected native collector, real Windows user | Explicit named contracts only, sequential sessions, transaction recovery, fresh input-bound evidence |
| historical | Original retained recipes and their external evidence | Dated audit mode; never new gameplay acceptance |

Candidate verification recompiles the matching checkout into a temporary
directory with the pinned compiler and finalizer, requires full PE equality,
then verifies the supplied PE directly. Machine-code expectations and helpers
are resolved from that candidate, not from a stale source-reference hash.
Archived release verification remains available separately.

Offline verifiers run in isolated scratch directories. Legacy assert-based
verifiers are explicitly launched with optimization disabled; infrastructure
protective checks use exceptions and are also tested under `python -O`.
No game is launched by CI/offline and no accepted archive is rewritten.

The stricter cache-flush fault probes form a separate visible review suite:

```powershell
./RunTests.ps1 -Suite faults -Config local.json
```

All three current native releases FAIL this additional OS-refusal requirement.
Behavior fixes must be validated separately from this source import.
An individual probe can also run independently:

```powershell
python -m infra.fault_probe --mod console --config local.json --output .local/console-flush.json
```

A proven hook remaining installed after injected OS refusal is FAIL. A broken
probe or an unexercised fault is BLOCKED. This is distinct from passing the
retained historical coverage; findings require separate behavior fixes.


Container Stack Fix is selected explicitly with `-Mod container`; the default
all-mod suite continues to use the frozen catalog. `container.build` checks the
clean source build, forced relocation, missing/unsupported/occupied modules,
repeated callbacks, protection/flush faults, races, rollback and helper lifetime.
`container.exact` binds these checks and 96 emitted-helper ABI comparisons to
the supplied candidate and supported client image. `container.baseline` records
the original disappearance without installing the plugin. `container.stacks`
checks two individual takes, returns, reopen, an independently confirmed reload,
full-stack rejection/capacity recovery, bloodpacks, a nonstackable weapon, the
native firearm-ammunition exception, and ordered vendor buy/sell operations.
The independent auditor rejects missing/replayed actions, mismatched rows,
quotes, inventory continuity, stock policy, wallet deltas and load receipts.

The container exact verifier also covers the server price helper in18 native
branch/local-state contexts, either module load order and coupled rollback.
Visibility is never published before the matching payment hook. Persistent UI
cache failure must retain payment, including during DLL unload.
