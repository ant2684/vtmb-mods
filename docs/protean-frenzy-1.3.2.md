# Protean & Frenzy Improved 1.3.2

Fixes the shared Claws animation filter assigning player-directed combos to
ordinary NPCs. This could leave the Serial Killer using kicks and combat
movement instead of normal Claws attacks. NPCs now retain the complete stock
AI pool; ordinary player combos and owned Frenzy keep their intended pools.

The only changed gameplay file is the native plugin. INI, male/female models,
particles, item definition and map resources are unchanged from1.3.1. The full
package remains eight game files plus one English manual and needs no previous
Protean package. Close the game before replacing files and restart afterward.

Qualification includes exact-DLL pools/weights/ABI, all native Claws activity
pools for NPCs, unchanged non-Claws forwarding, ordinary player chains, natural
Warform Frenzy and the actual Killer hostile callback including Beastform. The
owner accepted the installed correction. The original reference showed far,
far-left and low attacks; automated corrected-Killer sampling observed far-left
and low, while the far-only observation attempt remained incomplete. The full
stock candidate pool is preserved. Every enemy/quest encounter and arbitrary
third-party mod combinations have not been individually certified.

The runtime is the exact finalized, clean, tested binary; it was not rebuilt for
version metadata or packaging. Reproducible checks and precise limits are in the
module source and validation/Release.json. No diagnostic plugin, save, log or
modified gameplay Python belongs in the game archive.
