# Enemy damage and discipline reference — UP 11.5 Plus

Prepared for the Griffith Park Werewolf test package, 10 October 2026.
This is a technical reference, not a promise of final balance or an exhaustive
description of every native boss attack. Values below were read from the local
UP 11.5 Plus resources. **Declared**, **statically traced** and **observed in
play** are different evidence levels. No other bosses are modified by this pack.

## 1. Templates and combat parameters

| Template | Max Health | Strength | Dexterity | Stamina | Wits | Dodge | Calculated Combat Defense | Brawl | Melee | Firearms | Strata |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Werewolf, original UP | 80 | 2 | 1 | 5 | 6 | 5 | 11 | 0 | 0 | 0 | 7 |
| Werewolf, this test | 900 | 2 | 1 | 5 | 6 | 5 | 11 | 0 | 0 | 0 | 6 |
| SheriffMan | 570 | 4 | 5 | 5 | 6 | 4 | 10 | 5 | 0 | 2 | 5 |
| ManBat (Sheriff's second form) | 880 | 6 | 5 | 5 | 2 | 2 | 4 | 5 | 5 | 0 | 6 |
| MingXiao | 1400 | 4 | 4 | 4 | 3 | 0 | 3 | 3 | 4 | 4 | 6 |
| MingXiaoProxy | 325 | 3 | 4 | 1 | 0 | 1 | 1 | 3 | 3 | 1 | 4 |

Combat Defense is the `Defensive_Maneuvers` feat: **Wits + Dodge**, not
Dexterity + Dodge. The numbers above are calculated template values, not
runtime measurements after buffs, map events or control effects.

None of these base templates declares `Soak_Pool`. The test Werewolf also
leaves it undeclared, rather than adding an artificial soak pool. An omitted
pool is not evidence of zero *total* protection: equipment, feat rules and
active effects are separate inputs. The original Werewolf has no parent;
SheriffMan, ManBat and MingXiao likewise have empty `ParentTemplateName`.
MingXiaoProxy inherits MingXiao but overrides its listed attributes, abilities
and strata. It is not a second copy of the main boss's 1400-HP profile.

Additional declared attributes (original Werewolf values remain unchanged):

| Template | Charisma / Manipulation / Appearance | Perception / Intelligence | BloodPool / FaithPoints | Stealth / Computer |
|---|---|---|---|---|
| Werewolf | 1 / 1 / 1 | 6 / 5 | 0 / 0 | 0 / 0 |
| SheriffMan | 2 / 2 / 2 | 2 / 2 | 5000 / 10 | 0 / 0 |
| ManBat | 1 / 1 / 1 | 5 / 1 | 15 / 0 | 0 / 0 |
| MingXiao | 1 / 1 / 1 | 4 / 1 | 5 / 0 | 3 / 4 |
| MingXiaoProxy | 1 / 1 / 1 | 1 / 1 | 5 / 0 | 3 / 4 |

SheriffMan declares Fortitude 5 and Animalism 5. This does not by itself prove
that a particular buff is active during a particular fight. Its `General`
also declares `SpecialMoveADamage 25.0`; this is not a formula for every attack.
Werewolf's low Strength/Brawl entries must not be read as the complete native
monster-attack budget. No attack parameters are retuned in this package.

### Damage filters

| Template | Bashing | Lethal | Aggravated | Flame |
|---|---:|---:|---:|---:|
| Werewolf, original UP | undeclared | undeclared | undeclared | undeclared |
| Werewolf, this test | 0.20 | 0.40 | 1.00 | 1.00 |
| SheriffMan | 0.80 | 0.60 | 1.00 | 0.10 |
| ManBat | 1.00 | 1.00 | 1.00 | 0.80 |
| MingXiao | 0.75 | 0.80 | 1.00 | 0.30 |
| MingXiaoProxy | inherited MingXiao declarations | inherited | inherited | inherited |

The keys are `DamageFilterBashing`, `DamageFilterLethal`,
`DamageFilterAggravated` and **`DamageFilterFlame`**, not DamageFilterFire.
They are multipliers, not flat subtraction or percentages of armor. For
example, 0.20 retains 20% at the matching filter stage; it does not guarantee
that final HP loss will be exactly 20% of an unfiltered attack.

The test therefore heavily suppresses ordinary damage while not applying an
extra reduction to aggravated damage or fire. Fire has no extra vulnerability
bonus: its multiplier is 1.00. Original Werewolf's event-only damage path makes
missing filter declarations insufficient to predict its original killability.

## 2. How ordinary damage is processed

An actual attack must first reach the target through its trace/projectile/
collision path. Defense, soak, the damage record, type flags, template filters,
invulnerability/damage mode and class-specific reactions are distinct inputs.
Discipline control may use a separate AI schedule or trait effect rather than
an ordinary weapon hit. A particle or OnDamaged event alone proves neither
HP loss nor successful control.

The installed `feats.txt` lists the ordinary soak bases as:

- Bashing: `Armor_Rating + Stamina + Soak_Pool`.
- Lethal: `Armor_Rating + Soak_Pool`.
- Aggravated: `Soak_Pool`.

The listed Kindred bases for those ordinary categories match; falling has
separate rules. These are **pools used by feat/roll machinery**, not a rule to
subtract the pool's integer value directly from every packet. Fortitude's
level-1..5 trait effects add 1..5 `Automatic_Soak_Successes` when active.

Native static inspection of the supported server module confirmed that the
template loader reads the four filters and the damage callback multiplies the
damage-record coefficient by the selected one. Flame is selected by its flag;
otherwise the bashing/lethal/aggravated category selects the filter. This is
not a proven universal ordering/formula for every discipline and monster class.

The Griffith Werewolf has two confirmed native obstacles to ordinary damage:
its TraceAttack path zeros the relevant coefficient, and its native handling
uses an event-only damage mode. The unchanged clean VTM redirects the scoped
trace through the normal base-NPC path and uses normal damage mode during
native handling. Scope is the live, visible, named `werewolf` of the Werewolf
class on `sp_observatory_2`; other maps/actors/hidden phases retain their path.
Entity-handle checks protect post-call restoration. The server DLL on disk is
not patched. The VTM does not implement custom damage amounts or remove map
scripts at runtime.

The map supplied here already omits the UP `werewolf_hit_counter`, its melee/
ranged helper branches, `plus_check` and fixed `TakeDamage`/`fightWerewolf()`
outputs. The now-unused common Python function remains in `vamputil.py`; that
shared file is not replaced.

Stock `GetHealthPct` observations are **percentages**, not absolute HP. Earlier
100/55/2/0 samples must not be described as a 100-HP starting budget. Saved
observatory entities can retain older stats and outputs: use a save before
the first observatory visit for the current profile.

## 3. Flags, strata and target-specific rules

All listed bosses declare `Supernatural 1`, `Boss 1`, `NoBiting 1` and
`KnockbackRangedPlayer 1`. Werewolf declares `Kindred 0`; the two Sheriff forms
and both Ming templates declare `Kindred 1`. These are engine categories, not
a tabletop taxonomy assertion about Kuei-jin.

SheriffMan additionally declares `Monster 1` and `Disallow_Knockbacks 1`.
ManBat declares `Disallow_Kindred_Death 1`, `GibsCollide 1` and
`Has_Burning_Death 1`. Preserve these distinctions; declarations alone do not
fully describe scripted phase transitions and death behavior.

`DisciplineStrata` and `Supernatural` are compatible, not mutually exclusive.
Strata is a selector inside each ability's `Affects_Table`; Supernatural/Boss
are filters used by other rules. They are not automatically multiplied as two
independent resistance layers. Matching named-template rules can precede the
strata rules, which often precede the generic supernatural/boss fallbacks.
Some generic supernatural rules specifically require `No_Boss`.

Strata 6 is an existing resistant boss profile, **not uniform immunity, not a
global magic-damage percentage, and not uniformly stronger in every detail
than all other profiles**. Hit tables use `InheritFrom`; inherited schedules,
traits and callbacks matter. A table named `NoEffect` can still disorient or
play a reaction. The Werewolf now chooses the unmodified common Strata 6
profile, including Presence; no per-ability Werewolf patch is included.

### Confirmed named-template mappings in the discipline resources

These are real table declarations, distinct from the uncertain legacy
`Resistances` blocks below:

| Ability | SheriffMan | ManBat | MingXiao | MingXiaoProxy |
|---|---|---|---|---|
| Nightwisp Ravens | ordinary strata selection | ordinary strata selection | Supernatural_NoEffect | Supernatural_NoEffect |
| Spectral Wolf | explicitly Strata 6, although template is Strata 5 | Strata 6_No_Wolf | Strata 6_No_Wolf | Strata 2_No_Wolf, although template is Strata 4 |
| Hysteria | Supernatural_NoEffect | Supernatural_NoEffect | Supernatural_NoEffect | Supernatural_NoEffect |
| Mass Hallucination | Supernatural_NoEffect | ordinary strata selection | Supernatural_NoEffect | Supernatural_NoEffect |
| Trance | Supernatural_NoEffect | Supernatural_NoEffect | Supernatural_NoEffect | Supernatural_NoEffect |
| Blood Purge | ordinary strata selection | Supernatural_NoEffect | Supernatural_NoEffect | Supernatural_NoEffect |

No additional named-template mappings for these five targets were found in
the other main Animalism, Dementation, Dominate, Presence and offensive
Thaumaturgy tables. An unrelated target filter, map state or native limitation
can still matter. The Werewolf has no new named-template exception here.
For Spectral Wolf, the declared damage is 3–4% on Strata 6 and 30% on the
proxy's named Strata 2_No_Wolf branch. Do not substitute the proxy's nominal
Strata 4 to predict that particular ability.

## 4. Declared common Strata 6 reactions

These are table-derived **expected paths**, not guarantees that the Werewolf's
native class can perform every referenced animation/AI schedule. `Dmg_Health`
percentages are stock directives before subsequent native damage processing.
Do not equate them with final measured HP loss or introduce another reduction
without measuring. End/interruption damage describes alternative completion
paths, not an instruction to add both payouts for one cast.

### Animalism

| Level / ability | Declared Strata 6 behavior |
|---|---|
| 1 — Nightwisp Ravens | Human raven schedule, duration 2 seconds; Combat Defense −2 (also Hacking −2). Removal on damage/bump is declared. No custom one-second cap. |
| 2 — Burrowing Beetle | 2% health directive; inherits the Strata 5 branch with Knockback 50%. No human beetle execution schedule in this branch. |
| 3 — Spectral Wolf | 3–4%; supernatural escape schedule, duration 4 seconds, rather than the human fatal mauling branch. |
| 4 — Bloodsucker Communion | Bat activity for 3 seconds; 6–8% on end or interruption; removal on damage/bump. Its inherited Strata 2 branch has no explicit blood-return helper. |
| 5 — Pestilence | 6–8%; inherited incapacitation/swatting branch, duration 5–7 seconds, Chance_Effective 50%; not the human execution branch. |

### Dominate

| Level / ability | Declared Strata 6 behavior |
|---|---|
| 1 — Trance | Disorientation schedule for 3 seconds; not human trance. |
| 2 — Brain Wipe | Disorientation for 3 seconds; not human memory-wipe behavior. |
| 3 — Sleep | Disorientation for 3 seconds and Dmg_Health 0%; not prolonged sleep. |
| 4 — Possession | No possession AI schedule, no suicide-on-end and no damage directive; its 3-second visual-effect duration is not proof of 3-second control. |
| 5 — Mass Suicide | 6–8% plus 3-second disorientation; no human suicide schedule. |

### Dementation

| Level / ability | Declared Strata 6 behavior |
|---|---|
| 1 — Hysteria | Human hysteria schedule for 2 seconds; Combat Defense −2 (also Hacking −2); removal on damage/bump. |
| 2 — Mass Hallucination | Human hallucination branch for 20 seconds; Strength/Wits/Perception −2, plus Hacking −2. This relatively long effect is intentionally not custom-shortened. |
| 3 — Vision of Death | 4–5% with the supernatural madness-activity schedule for 6 seconds; not the fatal human branch. |
| 4 — Berserk Insanity | Disorientation for 3 seconds; no forced frenzy, side-switch or suicide-on-end schedule in this branch. |
| 5 — Voice of Bedlam | 6–8% and 3-second disorientation. |

### Thaumaturgy

| Level / ability | Declared Strata 6 behavior |
|---|---|
| 1 — Blood Strike | 2%, Knockback 50%, duration 2 seconds; end branch declares a 0.60-second flinch and BloodShot Return. Return's Strata 6 branch declares Heal_Blood 1; actual caster return remains a separate interaction. |
| 2 — Blood Purge | 3–4%; supernatural bloody-eye activity for 3 seconds; disorientation is declared on end without an explicit new duration there. |
| 3 — Blood Shield | Caster-side defense, not enemy-target damage/resistance; the stock declarations are Health_Buffer 80 and Health_Buffer_Block_Percent 50%, unchanged. |
| 4 — Blood Theft | Activity for 3 seconds; 6–8% on end or interruption, removal on damage/bump; selected branch has no explicit Bloodrip return/knockout helper. |
| 5 — Blood Boil | 5–7% and a 3-second blood-boil activity; no human fatal explosion schedule in this branch. |

The separate explosion/helper tables exist in the game, but their existence
does not prove that a Strata 6 cast selects them. Absence of instant kills is
a requirement, not a completed exhaustive runtime qualification.

### Presence and caster-side disciplines

All five common Strata 6 Presence branches inherit their corresponding human
trait effect: levels 1–5 reduce Strength, Wits and Perception by 1–5 respectively.
Level 4 also reduces Stamina by 2; level 5 by 4. They declare the normal daze
schedule, a 1-second gesture and Flinch 50%; aura lifetime follows the stock
mechanism (`Duration -1`), not a custom short control timer.

This is deliberately **not** the generic supernatural fallback discussed
earlier (no effect at 1–3, weakened effects at 4–5). Selecting common Strata 6
means using its existing Presence branches without an exception.

Caster buffs such as Protean, Fortitude and Blood Shield are not simply
cancelled by an enemy's target-table resistance. Protean claw hits have previous
actual-combat evidence on the native-damage fix. Frenzy's attacks/collision are
a separate workflow; the separate Griffith Frenzy fix is not bundled here.

### Strata 5 versus 6 examples

| Directive | Strata 5 | Strata 6 |
|---|---|---|
| Ravens / Hysteria duration | 3 seconds | 2 seconds |
| Beetle / Blood Strike | 4% | 2% |
| Spectral Wolf / Blood Purge | 6–8% | 3–4% |
| Communion / Pestilence / Bedlam / Mass Suicide / Blood Theft | 8–12% | 6–8% |
| Vision of Death | 6–8% | 4–5% |
| Blood Boil | 8–12% | 5–7% |

Original Strata 7 directs the main targeted tables for Animalism, Dementation,
Dominate, Presence and offensive Thaumaturgy to their supernatural no-effect
branches. Those branches differ by ability; do not generalize their names to
absolute lack of every visual or control reaction. Caster-side buffs remain
separate.

## 5. Legacy individual Resistances — declaration, not confirmed runtime rule

SheriffMan and main MingXiao have **no** `Resistances` block and no parent
supplying one. ManBat declares:

| Family | Full | Partial / Partial DMG |
|---|---|---|
| Dementation | Veil of Madness; The Haunting; Voice of Madness; Waking Nightmare | Total Insanity: Partial |
| Dominate | Calm; Dance; Follow; Hide; Jump; Leave | Mesmerize, Sleep, Possession: Partial; Impose Will: Partial DMG:0 |
| Thaumaturgy | Blood Malady; Theft of Vitae | Bloody Eye, Purge Blood: Partial; Blood Boil: Partial DMG:2 |

Original and test Werewolf declare **Full for every legacy name listed in
both columns of that table**. These declarations are preserved, not assumed
to override Strata 6. MingXiaoProxy declares no additional block.

The installed clandoc documents None/Partial/Full and a `Partial DMG:3` syntax,
but this is not proof of a live reader. Case-insensitive ASCII inspection found
no matching `Resistances`, `Partial DMG` or representative legacy-name reader
strings in the installed server/client/GameUI/top-level Bin modules. The
inspected server template-loader path reads General, Attributes, Abilities,
Disciplines, Numina and Reactions, but no Resistances section.

This strongly suggests obsolete declarations, **not complete proof that no
alternative reader exists**. Earlier interpretation as confirmed active
individual immunities was corrected. Do not claim Full overrides Strata,
rename these old abilities by guesswork, or interpret DMG:2 as a confirmed
two-HP/two-percent override. The named-template mappings in section 3 are the
confirmed resource-level individual exceptions.

## 6. Obfuscate and other native levers

`HasTrueSight` and `TrueSightVisionDistance` are read from **General**. The test
puts 1 and 150 there, with no duplicate Attributes declaration. Original UP
Werewolf instead declared HasTrueSight under Attributes; that declaration is
not proof the inspected General reader enabled it.

The native helper checks HasTrueSight and compares 3D distance against a nonzero
range; zero means no distance restriction in that helper. Stock templates use
finite distances, including 150 on a Sabbat ghoul. Actual Werewolf/Obfuscate
behavior, target loss after acquisition and bypassing early conditions remain
runtime questions. This is not a new detection system, a guaranteed 150-unit
discovery radius, or a change to stock Obfuscate attack bonuses.

Additional parsed General levers found in the native audit:
`Disallow_Knockbacks`, `Disallow_FirearmsToBashing`, `DisallowDiscipineTgt`
(engine spelling), `AbsorbsRangedAttacks` and `ReceivesExtraClubDmg`.
They are not added to the test Werewolf. Parsing a key does not establish its
complete class-specific effect or make it interchangeable with strata.

## 7. Death, scenario and current status

Ordinary OnDeath runs the existing clean completion function: persistent
one-time Alliance04 reward/death marker, death sounds, timer hiding and tram
trigger. It does not call Kill() or killWerewolf() again and does not add a
second corpse. The crush path keeps its tram-at-start and doors/switches-at-end
order; only reward/death marking share the guard. Alliance03 remains the
separate escape reward. No preparatory quest flag changes are required.

No regeneration is included. Earlier aggravated-claw observations left the
Werewolf's aggravated-wound stat zero while its total damage changed; that is
not a validated basis for selective healing. General HP healing is not used
as a substitute for distinguishing recoverable wounds.

The owner reported that the installed candidate looks excellent and requested
this test package for Wesp5, with further tuning expected. That feedback is
not exhaustive acceptance of every damage type, discipline, scripted crush,
corpse/reward uniqueness, tram/escape/reload, Frenzy or entrance scene.
Automated clean launches succeeded, but the current preparation runner did not
confirm active Protean 5 and stopped before real attacks. It is disabled.
Those remaining gameplay questions are being checked manually; no new game
launch or modification of installed gameplay bytes was performed for packaging.

## 8. Reproduction sources and native landmarks

- Werewolf/SheriffMan: `vdata/system/npctemplate001.txt`; ManBat: 012;
  MingXiao and proxy: 014. Original Werewolf compared against preserved UP input.
- Soak/defense: `feats.txt`; trait modifiers: `traiteffects000.txt`.
- Animalism/Dementation/Dominate/Presence/Thaumaturgy:
  `disciplinetgt_000.txt` through `disciplinetgt_004.txt`.
- Template loader: server RVA 1D3F00..1D4A34; strata read 1D494F;
  filter reads 1D49AF..1D4A25; TrueSight reads 1D4823/1D483C;
  inspected distance-helper range 146C2B..146CD2.
- Damage filter callback: 22F640, filter branches 22FAA2..22FC11;
  soak helper 22F4F0. RVAs refer only to the pinned supported server image.
- Native fixture SHA-256: vampire.dll
  `C546F4DE2003624D72F54D03805E0DBE1D8157231ADCC62368FF53FE6E48A76F`.

The source capsule retains the read-only inspection and technical regression
tools. Proprietary game inputs, personal saves, local paths, logs and backups
are not published in the source repository.
