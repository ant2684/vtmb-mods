# Griffith Park Werewolf — experimental maintenance source

UP 11.5 Plus test candidate for Wesp5; no public release version is assigned.
The owner reported positive first gameplay impressions and requested external
testing, with further balance tuning expected. This is not complete acceptance.

The clean native-damage VTM, Griffith BSP and scenario Python are unchanged
from the installed working candidate. The final template has 900 HP, original
Stamina 5 / Wits 6 / Dodge 5, no explicit Soak_Pool, Strata 6 including Presence,
General HasTrueSight 1 / TrueSightVisionDistance 150, and damage filters
0.20 / 0.40 / 1.00 / 1.00. Dexterity, attacks and legacy Resistances stay intact.
No regeneration or per-ability rewrites are included. Full technical findings,
Sheriff/Ming comparisons and uncertainty labels are in docs/ENEMY_REFERENCE.md.

## Inputs and independent checks

Keep proprietary inputs local. Supply the preserved original three resources
under an `original-root` with their Unofficial_Patch-relative game layout.
The original BSP is the pinned UP/accepted Griffith Frenzy-permission input;
do not use the already patched installed BSP as builder input. A mismatching
resource must stop the builder, not be rewritten with a generic replacement.

```powershell
python mods/werewolf/tests/test_resources.py --original-root <original-root>
python mods/werewolf/tests/test_inspection.py
python mods/werewolf/tools/verify_payload.py <payload-directory>
```

The resource tests cover Wolf-only changes, legacy declarations, map scope,
crush output ordering and completion idempotence using synthetic Python actors.
They do not substitute for real gameplay. `tests/wolf_damage_exact.c` exercises
the exact clean VTM through Windows PE loading with local supported server and
engine fixtures: signatures, occupied sites, protection refusal, x86 ABI,
normal damage-mode lifetime, map/hidden scope, unchanged packet and unload.

Build technical helpers and run exact checks with:

```powershell
./mods/werewolf/Verify.ps1 -Zig <zig-0.15.2> -Python <python> -Dependencies <pefile-dir> -GameRoot <game-root> -PayloadRoot <payload-directory>
```

`Build.ps1` is a clean-source rebuild recipe. A rebuilt VTM is a new candidate
until its exact identity and checks pass; never replace the delivered bytes
after gameplay qualification merely to re-strip them.

## Packaging and boundaries

`tools/package_test.py` reconstructs the pinned clean resources, verifies the
installed bytes, and exports the manual game-layout test ZIP. The user's
explicit additional English ENEMY_REFERENCE.md lives at archive root, outside
gameplay directories. It also exports a source capsule with one README.md,
technical scripts and required shared source helpers. No saves, proprietary
modules/resources, private logs, rollback copies or compiled test helpers go
into the source capsule or Git. The game-layout ZIP remains local, as do all
existing published gameplay archives; Git contains generators/source/docs.

This family is not registered as a finalized release in the common release
catalog. Existing common-runner dispatch remains unchanged; use these explicit
technical entry points. No new gameplay automation is added: the user took
over the checks after the local preparation runner could not confirm active
Protean 5. That runner remains disabled outside this portable source module.
Obfuscate, all discipline/class reactions, Frenzy and full scenario acceptance
remain manual. No game launch is part of packaging or these technical checks.

## Source origin

Original workspace implementation, imported from the Griffith Wolf task source.
Native behavior is unchanged; only the fixture include is adapted to the shared
repository helper. Resource builders reproduce the exact locally tested
candidate. The table inspector and English reference are new read-only tools
and documentation based on local UP resources. MIT applies to original source
and documentation under the repository LICENSE/NOTICE, not to game assets or
the Unofficial Patch. Native offsets/signatures are interoperability facts.
