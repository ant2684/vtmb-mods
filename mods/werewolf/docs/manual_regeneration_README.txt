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
Healing starts when the introductory scene reveals the combat Werewolf.
Load restoration reads the current saved battle state through the game-thread
lifecycle. Old queued start/stop/reset events cannot reset the healing deadline.
The Werewolf keeps stock protection from its own high-force roof shard blasts;
other damage and the scripted observatory crush remain separate paths.

Manual installation, game closed:
Back up each supplied file before copying Bin and Unofficial_Patch into the
game root. Preserve any existing INI and the original file timestamps. Also
back up griffith.pyc if present. Remove the backed-up griffith.pyc so the new
source imports. For an update with an identical BSP, leave that map and its
graph bytes and timestamps untouched.
If you already have an INI, keep your existing values instead of copying the
example settings over them. Saves already containing this mod's regeneration
actors are supported. For older saves without them, use a save BEFORE the first
observatory visit; those serialized maps are not migrated. Keep other plug-ins, saves
and video settings unchanged.

Rollback, game closed:
Restore the backed-up VTM, map, Python, any existing INI, cache and timestamps.
Remove only files introduced by this installation with no original. Do not
delete an INI that existed before installation or unrelated user files.
