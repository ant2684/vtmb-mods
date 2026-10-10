Griffith Park Werewolf - experimental test package for UP 11.5 Plus

For Wesp5 testing; further balance tuning is expected. Not a final release.
Requires a compatible Mod Loader that loads Bin/loader/*.vtm.
vampire.dll is not replaced. Keep existing compatible plug-ins, including any
separate Griffith Frenzy collision fix; that fix is not bundled here.

Profile: 900 HP, original Stamina 5 / Wits 6 / Dodge 5, Combat Defense 11,
no additional Soak_Pool, Strata 6, TrueSight range setting 150.
Damage multipliers: bashing 0.20, lethal 0.40, aggravated 1.00, fire 1.00.
No regeneration or custom discipline tables. Only the Werewolf is retuned.
ENEMY_REFERENCE.md describes the stock enemy/discipline rules, Sheriff and
Ming Xiao comparisons, native findings and remaining uncertainties.

Manual installation (game closed):
Back up all existing files that the supplied Bin and Unofficial_Patch folders
will replace, preserving their game-relative paths and original timestamps.
Also preserve Unofficial_Patch/python/griffith/griffith.pyc if present and
Unofficial_Patch/maps/graphs/sp_observatory_2.ain with its timestamp.
Copy Bin and Unofficial_Patch into the game root. After backing it up, remove
griffith.pyc so the supplied Python source is imported. Keep the existing AI
graph bytes and make its timestamp newer than the supplied BSP to avoid an
unnecessary graph rebuild. README.txt and ENEMY_REFERENCE.md are documentation;
do not copy them into gameplay directories.

Start from a save before the first visit to sp_observatory_2. Previously visited
maps can restore old entities, attributes and event outputs from the save.
Do not replace saves or change video settings. Other UP versions or conflicting
template/map replacements are not qualified. The native VTM fails closed on
unsupported native signatures or occupied damage/trace dispatch slots.

Manual rollback (game closed):
Restore the files and timestamps preserved before installation, including the
AI graph and Python cache. If no griffith.pyc originally existed, remove its
newly generated cache. Remove only a supplied file that had no original, such
as this VTM on a new installation. Keep all unrelated plug-ins and user files.
On an installation that already had the matching Wolf native-damage resources,
a template-only update/rollback replaces/restores only npctemplate001.txt.
