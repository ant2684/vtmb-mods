# Gameplay collection and recovery

Fresh gameplay contracts are listed by `./RunTests.ps1 -Suite gameplay -List`.
`console.minimize` observes the hidden native button, former button position and
cached title-menu availability, including reopening and reload. It uses the
supported five-second input scope, with an independent control audit; it does
not certify immediate input. It never creates a title menu by a memory write.
`console.minimize_remaining` is a bounded follow-up for a recorded early
menu-to-console opening failure: one first opening after a measured five-second
menu exit wait, then script pause and reload. It does not replay the full matrix.
`infra.console_minimize.audit_completion` independently audits the completed
workflows from both exact-candidate sessions while retaining the first FAIL and
its timing limitation. It never changes that first session into a PASS.
Each requires the exact supported modules, temporarily installed artifact and
actually selected resources. Nominate a save in local.json; do not substitute
the user's current quicksave or manufacture a PASS from a historical log.
`console.immediate`, `console.supported`, `history.bounded_resets` and
`history.transitions` have built-in collectors. Other fresh contracts require
a configured native collector; retained individual session scripts do not
automatically implement the new contracts. A named contract alone is not a
completed gameplay regression.
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
of resets because native entity allocation can grow. Missing gameplay certificates remain BLOCKED. History bounded v2 was actually
run and FAILed: after two gender changes the first fresh physical purchase did
not change native stats. A separate delayed diagnostic click also failed; the
UI showed zero physical points while raw stats had reset. Its first failure
is retained. This is a user workflow failure with unresolved code cause.

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


The live controller seals runtime hash/timestamp and settings observations
after stopping the owned PID. Delayed recovery uses that snapshot; a historical
PID alone cannot authorize overwriting newer user changes. Without a snapshot,
changed mutable files/settings remain BLOCKED for explicit reconciliation.
Scenario and preservation results have separate receipts. A behavioral FAIL
remains FAIL even when restoration is BLOCKED. Collectors/helper descendants
run in an owned kill-on-close Job Object, separately from the owned game.

Historical re-audit uses `-Suite historical -Mod <mod>` with
`historical.<mod>.evidence` configured to the original dated evidence tree.
Subtitle additionally requires `assets`; Background requires `game_snapshot`
from that historical run. The runner copies evidence before running the
retained auditor. Original first failures remain unchanged. Partial/PENDING
certificates are not PASS, and a dated audit never establishes fresh acceptance.


Current History audits require real action receipts and an independent native
UI command readback for rejected purchases. The latter observer is unfinished;
unchanged stats plus successful OS input cannot certify rejection. See the
review's scenario table for remaining collector gaps and fresh failures.

An unreadable process remains present in Inspect with Inspection=UNVERIFIED.
Do not assume a null StartTime means it exited. Such an observation blocks
launch and restoration until Windows no longer reports the process or an
operator resolves ownership. Console preparation failures retain their first
receipt separately from behavioral results; the collector does not retry
foreground acquisition or silently delay the immediate-input test.

After inspecting an unknown change, an operator can record an exact per-file
decision with `python -m infra.reconcile --config local.json --file <relative>
--sha256 <inspected-hash> --action keep-current --reason <decision>`.
This archives the current bytes and retains the original backup. Recovery
leaves that file untouched, verifies its approved hash/timestamp and reports
it separately. `restore-recorded` explicitly approves restoration of one
declared mutable output. Neither command accepts an unregistered path, a
changed inspected hash or a present/unverifiable game process. This is an
operator decision, never automatic ownership inference.

Partial restoration retains the installation lock and an explicit remaining
path list. Each restoration records its intent before replacing/removing bytes.
An incomplete partial restoration never reports a completed session or allows
another gameplay run.
