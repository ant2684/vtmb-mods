# Protean & Frenzy Improved 1.3.1

- Consolidates Protean/Frenzy lifecycle, inventory, melee, Claws buffer, shared
  stealth positioning and Griffith collision fixes into one native plugin.
- Handles naturally triggered Frenzy equipment even when map event Outputs are
  disabled, using original game scripts without a mod Python support file.
- Preserves stock Frenzy animation selection while keeping ordinary custom combos.
- Keeps model-pool separation active when InventoryFixes is disabled or unavailable.
- Includes persistent exact-DLL/model, configuration, ABI and fixture-priority
  regressions and a complete game-root package with one English manual.

The gameplay payload has eight files plus README: VTM/INI, two Claws models,
stealth sound/blood resources and two supported map resources. Native hunger
feeding rules are unchanged. Restore your original UP12 vamputil.py when upgrading
from the old Python-supported implementation; keep unrelated modifications.

The final option-isolation change passed256configuration masks,8invalid values,
232OS-failure cases,6exact DLL/model cases and one complete Inventory-disabled
gameplay scenario covering all seven ordinary chains, air/block and movement.
Earlier feature workflows retain their scoped qualification; this is not a claim
that every historical game scenario was rerun. Supported binary identities and
remaining limits are in the module's validation/Release.json.
