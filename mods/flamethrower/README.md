# Flamethrower damage numbers

Experimental native fix enabling the game's stock NPC damage floaters for
flamethrower hits. It changes only the immediate operand at server RVA
`3E3674`, from one to zero, in the flamethrower's no-floater setter call.
Damage, fuel, timing, filters, stats, saves and the on-disk game DLL are untouched.
The game's Damage Floaters option still controls visibility. Stock hit-value
semantics are retained; displayed values are not newly defined as net HP loss.

Original MIT workspace code. Signatures and offsets are interoperability
constants for locally supplied game files, not redistributed game code.
Compatible server SHA-256:
`C546F4DE2003624D72F54D03805E0DBE1D8157231ADCC62368FF53FE6E48A76F`.
Runtime guards check PE identity and four code anchors; unsupported/occupied
sites are left untouched. Only the owned operand is restored on unload.
There are no runtime logs, diagnostic exports, overlays or trampolines.

From the repository or source-capsule root, build with Zig (x86 Windows target),
Python, pefile and the shared finalizer:

```powershell
./mods/flamethrower/Build.ps1 -Zig <zig.exe> -Python <python.exe> -Dependencies <python-packages>
./mods/flamethrower/Verify.ps1 -Zig <zig.exe> -Python <python.exe> -Dependencies <python-packages> -GameRoot <game-directory> -Plugin <final.vtm> -PayloadRoot <manual-copy-directory>
```

Verification also requires Unicorn. The Windows fixture loads the exact finalized
plugin into its own synthetic process, maps a locally supplied native image and
checks signatures, occupied sites, API failures, ownership, one-byte change,
unload and protection recovery. It emits a patch certificate. Offline x86 flow
checks use the actual applied operand, compare full damage packets except the
suppression byte, execute the native setter/getter/queue branch and reject damage
changes. Compiler outputs and evidence stay in ignored build directories.

This candidate has its own explicit verifier. It is not a registered common
runner/release family and does not fall through another family's verifier.
No public version or gameplay acceptance is assigned. Manual in-game visual
acceptance on this exact clean candidate remains necessary; no automated game
launch is part of this task. Restart the game after adding/removing its VTM.
Source capsules preserve this layout and include the required shared tools,
with exactly one root README. Gameplay payloads contain the VTM and one English
manual README.txt only, without test programs or evidence.

Validation of the frozen candidate:
`0FD25AE14B5EB1BE32B5FF970E35A011A9889C5C48D0C6CD387D7059B2165ED6`
(15,872 bytes). The actual installed VTM and an independent source-capsule
extraction passed the standalone Windows fixture and eight native packet/queue
flow cases. Clean PE/payload membership, ZIP CRC/member equality and 147 existing
local-original identities passed. All 86 portable repository tests passed;
new authored source is provenance-covered without claiming external publication.
Gameplay visual acceptance is pending. No game process was launched for these
checks, and the frozen VTM was not rebuilt after finalization/testing.
