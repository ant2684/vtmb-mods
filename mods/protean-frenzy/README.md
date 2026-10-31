# Protean & Frenzy Improved 1.3.1

One native plugin combines Protean and Frenzy lifecycle, inventory, melee,
Claws combo input, stealth positioning and Griffith collision fixes.
Requires 32-bit Bloodlines, supported Unofficial Patch 12.0 and Game Mod Loader.
The game keeps its stock vamputil.py; no production Python component is supplied.

The complete game archive includes the VTM, INI, both matching Claws models,
stealth sound/blood resources and the two supported maps with Frenzy enabled.
It installs directly into the game root and needs no previous Protean package.
Read its English README before upgrading; remove the six replaced standalone
modules listed there and preserve unrelated mods and custom resource changes.

Eight INI options control the individual fixes. Matching models keep ordinary
custom combos separate from the stock Frenzy attack pool independently of all
options, including InventoryFixes=0 or unavailable inventory hooks. Model-pool
separation is a resource compatibility rule. Native hunger-Frenzy feeding rules
are preserved; multiple enemies do not universally prevent feeding.

## Source, build and regression checks

This module is a standalone source/test tree. It uses Python3, Zig0.15.2 and
pefile/capstone/unicorn. Supply your own supported game, original resources,
matching player-combo model inputs and nominated test saves. Personal saves,
full game DLL/VPK/BSP/MDL inputs, compiler/runtime tools and local paths are not
part of this source archive. Model input identities are pinned in the generators;
modified installed resources cannot be silently used as pristine inputs.

Copy local.example.json to ignored local.json and set your local paths/hashes.
From this module directory:

```powershell
python -B build.py --config local.json
python -B build_resources.py --config local.json
python -B build_maps.py --config local.json
python -B run_tests.py --config local.json --suite all
```

Build into a fresh output. Finalized bytes must not be rebuilt after acceptance.
The native signature and hook-ownership guards remain authoritative at startup.
Build/test Python programs do not install a Python gameplay dependency.

Focused model/option regressions:

```powershell
python -B run_tests.py --config local.json --suite all --only configuration pool_isolation claws_frenzy fixture_priorities native_runtime loader_compatibility
python -B run_gameplay.py --config local.json --pool-isolation-regression claws-actions-male
```

The exact-DLL fixture runs the original collector and both actual delivered
models with inventory enabled, disabled and blocked by a hook conflict. It
asserts ordinary7/Frenzy6 candidates, zero weights, ownership and x86 ABI.
The fixture-priority check prevents unsafe native-hunger target-ranking values.
Gameplay controls only its own process and restores files/mtime, saves, video
and shortcuts; temporary recovery copies are pruned after verified restoration.
Missing local game/save inputs block the requested test rather than count as PASS.

Repository CI runs source/synthetic checks only; licensed-input and gameplay
qualification is described in validation/Release.json. This standalone module
has explicit commands and is not a legacy common-runner release adapter.

Historical model alternatives and separate mods remain available in their own
directories. Do not load their replaced native implementations beside this one.
