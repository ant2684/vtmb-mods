# Console Pause Fix 1.0.1 maintenance source

Balances console-owned pause and completes native GameUI deactivation while retaining menu, ordinary and script pause ownership.

Based on the accepted 1.0.1 source capsule. The current maintenance candidate also hides the console Minimize button on each opening and disables Minimize in an existing title menu, using guarded stock methods. It adds no detours. Frozen release archives remain unchanged; this behavior change has no new public version yet.

From the repository root:

```powershell
./RunTests.ps1 -Suite ci -Mod console -Config local.json
./RunTests.ps1 -Suite offline -Mod console -Config local.json
./RunTests.ps1 -Suite gameplay -Mod console -List
```

Use `console.minimize` with an exact matching clean `-Candidate` for fresh button/title-menu observations plus the supported console transitions. Input coverage includes the measured external five-second wait; it does not certify immediate input. Raw first failures are preserved and checked separately from installation restoration.
Frozen release verification uses the pinned harnesses from its unchanged source capsule. Candidate verification uses this checkout's extended harnesses; neither path silently substitutes binaries or transfers the new control coverage to the older release.

Use pinned Zig 0.15.2/Python dependencies. Offline requires the frozen release directory and supported local game modules; missing inputs are BLOCKED. See the root docs for exact candidate verification, scenario limitations and recovery. Retained local Session/Install scripts are historical recipes; inspect and adapt them before use. Do not run an installation recipe merely to audit evidence.

Sources and technical checks are separate from the manual gameplay payload. Existing accepted ZIPs and source capsules remain byte-identical. Exact final bytes require renewed technical and relevant gameplay evidence after any behavior change.
