# Container Stack Fix

Original MIT source for an unreleased, standalone Bloodlines loader candidate.
Native signature bytes identify interoperability with a locally supplied game;
no game module, save or recording is distributed.

The client duplicate filter hides an already-owned item even when its resource
allows stacking. A guarded client hook exempts only stackable donor
items after the original ammunition exceptions. Inventory mode, nonstackable
items and native transfer rules remain original. A separate client action hook
disables Give/Sell when the receiving stack reaches its native stack limit,
and re-enables them after capacity becomes available.

A second guarded server hook fixes the Buy price flag for stackable items.
The original code treats an already-owned knife as an ammunition purchase
and charges its zero ammunition worth. After the native IsStackable test,
only its stackable branch clears that local flag; the original price formula,
nonstackable ammunition branch, stock policy, Take and Sell are retained.
The loaded_client/loaded_server callbacks accept either module order and expose
duplicate rows only after both supported modules and the payment patch are ready.

The visibility helper replays the original UI mode read, preserves registers, ESP and flags,
calls the donor's IsStackable thiscall, and branches to the original show/skip
continuation. It contains no plugin pointers. Once published its single page
stays allocated until process exit, so cached/in-flight jumps remain safe even
if cache flushing or unload restoration fails. Published failures do not retry
installation. All three helpers have no plugin pointers and retain their published pages.
Module identities, native anchors and all three occupied sites are checked. If UI
cache rollback cannot be confirmed, the payment hook remains installed as well.

## Requirements and commands

Use the repository local configuration with pinned Zig 0.15.2, Python 3.12 and
local `pefile`, `capstone` and `unicorn` packages. Supply the supported game
modules locally. The supported client SHA-256 is
`E88BEAE0DD03AF06493C71C5E8D87A6993B54E590CB6AD37CD3513C588582870`.
The supported server SHA-256 is
`C546F4DE2003624D72F54D03805E0DBE1D8157231ADCC62368FF53FE6E48A76F`.

Build using `Build.ps1 -Zig <zig.exe> -Python <python.exe> -Dependencies <packages>`.
The shared runner has `container.build` (synthetic native install/refusal plus
exact helper ABI), `container.exact` (the exact supported game module),
`container.transfer` (focused knife/cap confirmation), `container.baseline`
(unpatched disappearance) and `container.stacks` (fresh
UI workflows and independent native-state audit).

Select `-Mod container -Candidate <finalized.vtm>` for offline/gameplay runs.
Supply `saves.container` as an archival Item Issue save. The baseline deliberately
does not install the candidate. Gameplay runs own their PID, files, settings and
temporary save via the common transaction and retain failures. Configure
`container_baseline` with the successful unpatched observations.json before
running the fixed scenario. No scenario is
accepted merely from OS input or a generic observed=True flag.

The native harness loads the actual finalized VTM at a forced relocated base,
injects API faults and tests guards, repeated installation, rollback, protection
and helper lifetime. Unicorn runs the emitted helper in 48 original-machine-state
comparisons (96 original/patched executions) including different UI modes, stackability, null donor and register
seeds. Another 18 price-helper contexts compare the original branch, registers,
flags and every local byte, including unchanged nonstackable ammunition pricing.
Only a final clean binary tested in the game may enter the gameplay ZIP.

Export with `python -m infra.export_capsule --mod container --reference <vtm>
--output <source.zip>`. Validate the independent extraction with
`python -m infra.export_validation --mod container --config <local.json>
--output <report.json>`. The candidate has no frozen public release/version.


The gameplay audit requires both knives taken individually and returned,
reopening, a real save/load after deliberately changing ownership, full-stack
rejection and capacity recovery, bloodpacks, a nonstackable sledgehammer and
the native ammunition row. Vendor checks use displayed pre-click prices and
actual money/count deltas for repeated buys, sales and buyback. Authored vendor
stock can remain available after a buy; the native stock table determines the
expected donor delta. These are test requirements, not a claim that every
client revision or vendor has been tested.


The vendor regression uses the real Trip and his original dialogue in
sm_pawnshop_2. Native dialogpick supplies the command-client context. The
finite-stock receiver regression sells ten silver rings, reopens barter with
one more ring, rejects Sell at ten, buys one to free space, then sells it back.
Native displayed prices, wallet changes and both owners are audited. The
container counterpart fills the fridge with Give, rejects at ten, takes one
and gives it back. This fixture does not change the original save/resources.

`tools/package.py` accepts the exact-binary report and successful fresh
container.stacks observations. It refuses mismatching candidate bytes or an
unfinished restoration, then writes the manual game-layout ZIP and matching
source capsule. Validate that final source archive from a separate extraction
before delivery. There is no installer, automatic installation or public version.

The receiver hook at client RVA16FE4A preserves machine state and only raises
the existing full-stack local for Give/Sell. It uses the active donor cache,
validated EHANDLEs and the native item-data index/stack limit. The native disable
path also gates double-click dispatch. Existing server Inventory_Can_Insert
checks remain authoritative. Exact helper checks cover both sides of the limit,
other action kinds, inventory mode, nonstackable items and stale handles.
