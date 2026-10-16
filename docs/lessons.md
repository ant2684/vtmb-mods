# Lessons retained in executable checks

The latest user requirement defines the expected result. Acceptance, packaging
authorization and external publication are separate events. A historical PASS
only applies to the exact recorded inputs and scope.

| Requirement | Scenario / expectation | Verification / evidence |
| --- | --- | --- |
| Deliver exact clean bytes | `packages`, `<mod>.exact`; frozen membership and PE identity | CRC, safe raw paths, payload/source identities, PE imports/exports/debug/overlay checks and before/after hashes |
| Native hooks must refuse unsupported/occupied sites | `<mod>.build`, `<mod>.exact` | Native/emulated signature, ABI, relocation, fault and partial rollback harnesses; OS failure findings remain visible in review |
| Closing console must restore control | `console.supported`, `console.immediate` | Native receipt, signed movement, camera and resumed world; measured five-second wait belongs only to supported scenario |
| Repeated Frenzy must not accumulate bonus | `protean.lifecycle` | Native Shadow count, feats before/after repeated request, both end orders, load/map cleanup |
| P4 and RedVision have independent state | `protean.filter` | Reload/off ConVar plus observed brightness and separate RedVision |
| Model alternatives have different real bytes | `protean.models` | Both editions and both sex variants, donor chains, signed links, metadata, intentional corruptions and reconstruction |
| Four-hit is actual combat behavior | `protean.fourhit` | Four ordered native damage windows and actual model sequences, termination, interruption/restart, block |
| Frenzy area permission and collision are separate fixes | `frenzy.library`, `frenzy.griffith` | Exact selected BSP; native Frenzy and living target contact, forwarding and cleanup; Griffith cannot certify Library |
| Radio needs real time and actual audio | `subtitle.radio` | First/repeat/on/off/TV/load transitions and complete unaccelerated PCM/decoder/caption loop |
| Hide the background, keep the text | `background.cinematics` | Two native cinematic fades, no fill/border, exact text/bounds, ordinary dialogue and load/map |
| Gender changes reset purchases, bonus and full fresh pool | `history.transitions` | Actual prior allocation to complete reset, new purchases, rejection after exhaustion, Base/Sheet/Accept |
| History reset has a finite entity budget | `history.bounded_resets` | Bounded sequence and recorded slots; no promise of unlimited switching |
| Preserve personal game state | infrastructure / transaction tests | Write-ahead intent, lock, corrupt backup/unknown changes/uncertain launch rejection, byte/timestamp restore and archived changes |

Visibility, world pause, sound and control are separate observations. An OS
SendInput receipt or a console command is not proof that the game completed it.
First failures are immutable; diagnostic follow-ups have their own results.
Coverage expands only for a different transition, code path or observed defect.

Finalize PE bytes before final tests. Required signatures, relocations, CRT/TLS
and protective code are not debug debris. Rebuilding or stripping tested bytes
requires new evidence. Keep diagnostics out of gameplay payloads.

Every future mod should start with a named requirement and transition catalog,
refusal/rollback tests, clean payload checks and a script entry point. Prefer a
shared implementation for common helpers and verify exported source capsules
without the original workspace. Do not turn a discovered defect into a passing
expectation merely to obtain a green dashboard.


The complete History creation pool means actual spendable category points,
not a guessed XP constant. A native allocation reset and positive XP can coexist
with exhausted UI category points. Observe purchases and rejection after
exhaustion. Preserve the incorrectly specified test and correct its version;
do not turn the subsequently observed workflow failure into PASS.
An observer table size is not an allocator budget. A stale recorded PID is not
ownership of later user changes. A cleanup failure must not replace the first
scenario result. Capture runtime output hashes after the owned process stops,
and require them when delayed recovery restores personal configuration.


Container candidates must stay separate from frozen public release identities.
Exercise the actual finalized VTM with forced relocation and a synthetic/real
client image, then run emitted helper bytes against original registers, flags
and stack state. A published standalone helper must remain callable after a
failed cache flush or unload restoration; freeing published code can leave
cached or in-flight jumps pointing into released memory.

For container gameplay, a click or unchanged before/after count is insufficient.
Observe server owners/counts and the live client row/action separately. Save,
change ownership deliberately, then confirm a new player and restored saved
inventory. Bind trade quotes to the selected native entity and action before
the click; verify money and the native authored stock policy afterward.

Bloodlines evaluates Python when submitting console text; an engine cfg command
buffer is not equivalent. Trading additionally requires the server command-client
context. SyncVendorInventory reads that context even when StartBarter already
received a player. Drive the original dialogue response through the native HUD
instead of scheduling a Python StartBarter call outside a client command.

For a full-stack fixture, GiveItem creates the item but repeated calls do not
add copies. The native GiveAmmo API also increases counts for stackable items;
UP uses it for bloodpacks and other stackable goods. Confirm the native count
before testing capacity. Avoid clicking an already selected row again: a
second row click can trigger the native double-click transfer.


Making duplicate stackable vendor rows visible exposes an original server
price bug: the Buy handler passes an already-owned flag as the ammunition-price
flag, so an owned knife costs zero. Correct that local flag only after the
native IsStackable branch; retain the original nonstack ammunition path and
price formula. Install payment before visibility. If restoring the visibility
site cannot be confirmed by an instruction-cache flush, retain the standalone
payment helper as well. Test quantities and money together: row visibility
and a successful transfer alone would miss this regression.
