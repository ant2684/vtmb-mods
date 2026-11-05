**Fixes & Adjustments 1.2**

Nine configurable fixes for **Vampire: The Masquerade – Bloodlines**. All nine are enabled by default.

## What it fixes

The examples below describe the original bugs. To compare behavior, set the corresponding INI option to **0** and restart the game.

**Console Pause Fix**

Open the console during gameplay and close it with **X**. The game can remain paused or fail to return control to the player. The fix releases the console’s pause and restores input while respecting any pause that was already active.

**Subtitle Pause and Radio Fix**

Pause while the pawn shop radio is speaking, then resume. Subtitles can advance during the pause and fall out of sync with the audio. Turning the radio off and back on can also bring back stale captions.

**History Stat Reset Fix**

Spend points manually or use **Auto-Spend** during character creation, then change gender. The character resets, but some points can remain marked as spent. The fix restores the full starting allocation.

**Container Stack Fix**

Take one item from a stack in a container. The remaining items can disappear from the list. The fix also corrects repeat purchases that can become free and disables **Give** or **Sell** when the receiving stack is full.

**Container Input Guard**

Press **Enter** or **Space** with a barter button focused in an open container. The key can activate the button and close the container unexpectedly. The guard blocks those keys on barter buttons and prevents the inventory-close command from closing an open container.

**Flamethrower Damage Numbers**

Turn on **Damage Floaters** and hit an enemy with the flamethrower. The hit deals damage without displaying a number. The fix makes flamethrower hits show damage numbers.

**Casting Animation Cleanup**

Fire a weapon, start casting **Possession**, then immediately load a save. The character can remain stuck in the casting animation after the reload. The fix clears the leftover casting state.

**HUD Indicators Fix**

Health and blood animations can freeze after changing location or loading a save. Full indicators can also appear slightly underfilled. The fix prevents these animation freezes and aligns the fill with the indicator frames.

When feeding through dialogue, the victim’s blood bar can start partially filled despite a full blood supply, then decrease in jumps. The fix corrects its initial fill and makes it decrease smoothly, matching normal feeding.

The player’s blood indicator still becomes static at full blood, as in the original game.

**Loading Input Guard**

Select a taxi destination and keep holding the left mouse button through loading. Your character can attack on arrival without a fresh press. The guard requires you to release and press again after loading.

## Requirements and installation

Requires **Unofficial Patch 12.0** with the **Advanced EXE / VTM loader**.

1. Close the game and back up any files you plan to replace.
2. When updating, remove previous standalone versions of the included fixes.
3. Copy the archive’s **Bin** folder into the game directory and merge it with the existing **Bin** folder.

Keep the supplied plugin filenames. Loading Input Guard loads after **vtmb-dialogue-mouse** if you use it.

## Configuration

Open **Bin/loader** and edit **ant2684-fixes-adjustments.ini** for the main fixes or **vtmb-loading-input-guard.ini** for Loading Input Guard.

Set an option to **1** to enable it or **0** to disable it, then restart the game. **HUDIndicatorsFix** controls the health, blood and victim-bar fixes together.

## Acknowledgements

Special thanks to **Wesp5** for his continued work on the **Unofficial Patch**, and to the **Bloodlines community** for sharing knowledge, reporting bugs, and keeping the game alive.
