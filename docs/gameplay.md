# Gameplay collection and recovery

Fresh gameplay contracts are listed by `./RunTests.ps1 -Suite gameplay -List`.
Each requires the exact supported modules, temporarily installed artifact and
actually selected resources. Nominate a save in local.json; do not substitute
the user's current quicksave or manufacture a PASS from a historical log.
`console.immediate` has a built-in first-event collector. Other fresh contracts
currently require a configured native collector; retained individual session
scripts have not been converted automatically.
An absent collector or save produces BLOCKED before any game change.

Set `gameplay_commands.<scenario>` to an argument array for a reviewed
collector. `{python}`, `{repo}` and `{session}` expand to current paths.
`VTMB_GAME_ROOT`, `VTMB_SESSION` and `VTMB_IDENTITY` are passed in its environment.
The runner owns launch/installation/restore: collectors must not launch/kill
other games, change video settings, replace unregistered files or restore a
different session. Register required runtime output paths in `runtime_outputs`
before launch. `model_archive` selects an exact accepted Four-hit edition.

The collector writes `observations.json` in the session directory. It must
bind the session/scenario/version, artifact/module/resource/save hashes to
identity.json, preserve the first result, provide all named native before/after
records, native observation sources, measured durations and requirement-specific
metrics. Missing/stale/duplicate records or OS-only input receipts are rejected.
The immediate console case has a 250 ms collection scheduling budget after
native observed close; this is a test validity limit, not a gameplay delay.
The radio correlation threshold is a collector screening threshold, not
general proof of speech timing correctness. Keep raw observations separately.

Library requires the exact shipped Library BSP and its own nominated save.
Four-hit needs a suitable living target and four independently observed hit
windows, plus interruption/restart/block. History tests use a bounded number
of resets because native entity allocation can grow. These missing gameplay
certificates remain BLOCKED until a real fresh collector run establishes them.

Before mutation, the executor refuses a user-owned running game and captures
real launch-user HKCU Settings/ResPatch, shortcut arguments, file bytes and
save timestamps. It uses `-game Unofficial_Patch -dev -novid -console` with a
verified hyphen-free temporary save and omits video flags and `-condebug`.
It stops only its recorded PID with matching creation time. Changes to
registered files are archived before restoration; only registered task files
are removed. Unrecognized changes stay intact and block recovery.

An installation-wide Windows mutex, persistent `.vtmb-regression.lock` in the
game root and durable journal retain unfinished sessions. Different evidence
directories cannot bypass the installation lock. Recovery:

```powershell
python -m infra.recover --config local.json
```

Recovery is idempotent. The lock remains until bytes, timestamps and real-user
settings are verified restored. Damaged backups, unknown changes or a launch
intent without a captured PID require explicit inspection and reconciliation;
the executor never guesses process ownership. Keep all evidence and originals
until resolved. Infrastructure tests exercise failures on isolated fixtures;
they do not certify a real gameplay session or permission to change resolution.
