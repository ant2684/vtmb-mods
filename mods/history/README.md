# History Stat Reset Fix 1.5.1 maintenance source

Resets History and purchases on gender changes, returns the full fresh creation pool and protects one-shot funding. Unlimited reset endurance is not promised.

Imported from the unchanged accepted source capsule. Native plugin behavior is unchanged; shared helpers, test entry points and documentation are maintained here without a public version increase.

From the repository root:

```powershell
./RunTests.ps1 -Suite ci -Mod history -Config local.json
./RunTests.ps1 -Suite offline -Mod history -Config local.json
./RunTests.ps1 -Suite gameplay -Mod history -List
```

Use pinned Zig 0.15.2/Python dependencies. Offline requires the frozen release directory and supported local game modules; missing inputs are BLOCKED. See the root docs for exact candidate verification, scenario limitations and recovery. Retained local Session/Install scripts are historical recipes; inspect and adapt them before use. Do not run an installation recipe merely to audit evidence.

Sources and technical checks are separate from the manual gameplay payload. Existing accepted ZIPs and source capsules remain byte-identical. Exact final bytes require renewed technical and relevant gameplay evidence after any behavior change.
