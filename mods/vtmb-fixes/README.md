# Fixes & Adjustments 1.2

Eight fixes and adjustments in one VTM and INI. Loading Input Guard has its own VTM and INI. Both plugins ship in one game ZIP with one README.txt.

The original algorithms are compiled as separate translation units with
namespaced callbacks. `native/runtime.c` routes the real loader callbacks
according to startup configuration. `native/container_input.c` reimplements
the installed third-party Enter/Space and container-close behavior with guarded
publication, reverse rollback and self-contained executable helpers. Published
helpers contain no pointers back into the VTM and remain allocated until process
exit, so a failed restoration cannot jump into an unloaded DLL. This is not a
general hot-unload guarantee for the other process-lifetime components.

`input-provenance.json` records the original source inputs. Component internals
retain their original support guards. A missing option defaults to enabled;
an explicit value other than `1` disables only that option. A restart is required.

## Build and native verification

Use Python 3, Zig 0.15.2 and pefile/capstone/unicorn. Supply paths explicitly;
no game binaries, toolchain, saves or personal local configuration are included.

```text
python build.py --zig ZIG --deps PYTHON_DEPS --game GAME_ROOT --out BUILD_DIR
python run_tests.py --zig ZIG --game GAME_ROOT --plugin BUILD_DIR/ant2684-fixes-adjustments.vtm --guard BUILD_DIR/vtmb-loading-input-guard.vtm --out CHECK_DIR
```

Check the command's `--help` for exact arguments. Build and check directories
must be separate from active loader directories. Finalization happens before
verification. Never rebuild, strip or change the qualified delivery afterward.
The clean build is bound to the supported engine/client identities; native
fixtures execute the actual finalized VTM, including all 256 main-package option masks,
invalid values, callback orders, original component fixtures and container input
behavior/ABI/OS-failure/unload-lifetime cases. The subtitle source fixture is
supplementary evidence, not a substitute for in-game synchronization checks.

## Owned game verification and preservation

`deployment.py` is an internal development transaction tool, not an installer.
It preserves one original recovery set outside the game, snapshots settings,
and restores all test writes before final installation. It keeps the owner-
approved newer Library map and Python. Its pinned hashes intentionally refuse
unexpected release inputs. Never run it against a user game already running.

`tests/gameplay.py` launches a dedicated game process and preserves the active
video settings.

Loading readiness requires actual clock advancement and completion of the
loader's distinct click wait; a serialized player alone is insufficient. The
loading recipe exercises a full physical press/release followed by the first
fresh in-world attack. This loader will not continue while the button is held.

The original loading guard has a new bounded compatibility path for the reviewed
separate `vtmb-dialogue-mouse.vtm` (975F4F5E...). It checks PE identity, relocated
handler bytes, client binding and the native trampoline/return. Only that owner
is forwarded. Unknown hooks fail closed and partial installation rolls back.
The guard filename sorts after vtmb-dialogue-mouse.vtm. Native tests cover
forwarding, disabling the guard and six mismatches. No generalized detour chaining or hot-unload guarantee is claimed.

Build/native tests are self-contained in this capsule. Optional complete gameplay
recipes reuse the retained workbench observers supplied through `--repo`.
Use nominated saves with explicit SHA-256. Keep diagnostic evidence outside
the active game and remove helpers afterward. Optional owned-test sources select
the original wizard action and observe the native damage-number queue; neither
helper is part of the gameplay ZIP. They run only for the owned process lifetime. Full scenario results and known
limits must be recorded independently from native technical PASS and from
owner acceptance. Frozen release history is supporting evidence only.

## Packaging

The gameplay ZIP contains both VTM and INI pairs under `Bin/loader` and one
`README.txt`. The source ZIP contains the build scripts, sources and test fixtures.

## HUD integration - 5 November 2026

HUDIndicatorsFix controls both HUD components as one group. Native algorithms
come from the qualified side/victim modules recorded in hud-input-provenance.json.
Their standalone INI and attach callbacks are removed; runtime routes both through
the central switch. No separate HUD plugin is shipped. Signature generation
accepts the reviewed Advanced EXE horizontal-scale operand while preserving its
value. Existing seven features and the separate loading guard are unchanged.

Focused integration checks cover all-off, old features only, HUD only, all-on,
invalid HUD value and reverse callback order, plus exact compiled HUD fixtures.
A short owned-game smoke confirms both HUD components after standalone removal.
Historical full matrices remain documented separately; no new broad game replay.

The historical deployment.py helper retains its original split-release input
pins. Current integration/migration is recorded in validation/HUDIntegration.json;
use current build/check/package commands, not the historical deployment preset.
