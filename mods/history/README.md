# History Stat Reset Fix 1.5.2 maintenance source

Resets History and purchases on gender changes, returns the full fresh creation pool and protects one-shot funding. Unlimited reset endurance is not promised.

Current native source reinitializes the creation Sheet category counters through the stock ClanDoc initializer after a server reset. This fixes Auto-Spend and manual allocations remaining spent after a gender change. No client code hook is installed and existing Experience is preserved; an explicit native creation flag limits the added operation. The user accepted this correction and authorized release packaging on 2026-10-06.

From the repository root:

```powershell
./RunTests.ps1 -Suite ci -Mod history -Config local.json
./RunTests.ps1 -Suite offline -Mod history -Config local.json
./RunTests.ps1 -Suite gameplay -Mod history -List
```

Use pinned Zig 0.15.2/Python dependencies. Offline requires the frozen release directory and supported local game modules; missing inputs are BLOCKED. See the root docs for exact candidate verification, scenario limitations and recovery. Retained local Session/Install scripts are historical recipes; inspect and adapt them before use. Do not run an installation recipe merely to audit evidence.

Sources and technical checks are separate from the manual gameplay payload. Packaging preserves the exact tested plugin bytes. Exact final bytes require renewed technical and relevant gameplay evidence after any behavior change.

For the finalized candidate, run the exact technical checks with `-Suite offline -Mod history -Candidate <path>` and the retained bounded native gameplay workflow with:

```powershell
python -B -m infra.history_auto_session --config local.json --mode candidate --candidate <path> --full
```

The runner owns preservation, temporary installation, process control and restoration. It preserves video settings and checks native UI counters plus real purchases, repeated Auto-Spend, stock Reset Stats, actual bonus History, reverse gender, Base/Sheet and Accept. The recorded input geometry requires fullscreen 2560x1440; adapt input coordinates instead of changing video settings. `--mode baseline` and `--mode stock` are diagnostic comparisons, not gameplay acceptance certificates.
