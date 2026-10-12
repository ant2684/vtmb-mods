Griffith Park Werewolf regeneration - local experimental candidate

Requires UP 11.5 Plus, compatible Game Mod Loader and the matching Wolf
native-damage map/scenario. This is not a final release. Existing balance
settings in npctemplate001.txt are not replaced. All damage types can heal.

Settings: Bin/loader/griffith-wolf-native-damage.ini
[Regeneration]
HPPerTick=5
TickIntervalSeconds=1.0

Restart the game after changing settings. HPPerTick is an integer >=0; zero
disables regeneration only. Interval is finite and >=0.1 seconds. An absent
INI uses 5/1 defaults; an invalid or unreadable INI disables regeneration.
Use ASCII or UTF-8 text, with a dot for the decimal separator.
Healing cannot exceed the actor's current maximum or revive a dead actor.
It uses game time, not frame count; pause/load do not grant missed ticks.

Manual installation, game closed:
Back up each supplied file before copying Bin and Unofficial_Patch into the
game root. Preserve any existing INI and the original file timestamps. Also
back up griffith.pyc if present and maps/graphs/sp_observatory_2.ain. Remove
the backed-up griffith.pyc so the new source imports. Keep the graph bytes,
making its timestamp newer than the updated BSP to avoid a graph rebuild.
Use a save BEFORE the first observatory visit; old serialized maps without
the new timer are not automatically repaired. Keep other plug-ins, saves
and video settings unchanged.

Rollback, game closed:
Restore the backed-up VTM, map, Python, any existing INI, cache and timestamps.
Remove only files introduced by this installation with no original. Do not
delete an INI that existed before installation or unrelated user files.
