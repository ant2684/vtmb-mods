# Release and regression review

Later disposition (2026-10-06): History 1.5.2 fixes the pool failure recorded
below. Its existing server reset now calls the stock ClanDoc category
initializer under the explicit creation flag, with validated client signatures,
no client hook and no synthesized XP. The clean exact binary passed the37
server cases and13 additional client/pool/ABI cases. Distinct Auto-Spend and
manual History/gender transitions, new purchases, repeated Auto-Spend, stock
Reset Stats, Base/Sheet and Accept were verified; the user accepted the result
and selected1.5.2. Unlimited reset endurance remains outside the claim.
The old configuration was restored following the user's choice. The following
initial review and first FAIL observations remain historical.

This review covers the six current release families and their imported maintenance sources. Protean includes the shared Core and both accepted model alternatives. The Melee Frenzy prototype is outside the review. Current archives remain unchanged. Fresh owned History sessions temporarily installed the exact release and were fully restored, including real-user settings and shortcut arguments. No permanent installation was performed. Fresh runs exposed a failed spendable-pool workflow; technical PASS results do not certify it.

The release record identifies twelve gameplay archives and six source capsules. Existing technical and gameplay certificates apply to their recorded artifacts and supported native modules; importing sources or passing CI does not extend that acceptance to new binaries, new module versions or previously untested workflows. Current delivery archives must remain unchanged.

## Initial implementation findings and disposition

- **P1 — Candidate propagation.** At review time, `infra/runner.py` accepts `--candidate` but does not pass it to `infra/gameplay.execute`. The latter verifies the frozen release and installs its archive. A gameplay candidate request therefore exercises the release instead. Pass the candidate and its verified identity through preparation, installation, evidence and restoration, or reject this option for gameplay until supported. Never silently substitute artifacts.
- **P1 — Fresh collectors are incomplete.** `infra/gameplay.py` declares scenario contracts but requires user-configured external collector commands. Existing historical collectors do not emit this new contract automatically. Supply inspected adapters for the existing workflows and runnable targeted collectors for new workflows. Until then, the relevant tests are `BLOCKED`, not implemented gameplay regressions.
- **P1 — Audit predicates do not yet establish every requirement.** Generic `expected=true`, `observed=true` and nonempty before/after dictionaries are insufficient. In particular, `frenzy.library` has no requirement-specific predicate proving permission, native Frenzy, owned Shadow and cleanup. Add predicates derived from native observations for every required transition, including console pause ownership, menu restoration and reload. Add negative tests using plausible but incorrect states; a label asserting success must not replace an observation.
- **P1 — Installation locking must identify the installation.** `infra/session.py` places the lock under the configurable state directory. Two state directories permit concurrent transactions against one game directory. Use an installation-keyed process lock or an equivalent shared lock independent of the chosen evidence directory. Test two distinct state roots against one installation.
- **P1 — Check all running games before file restoration.** The gameplay `finally` block stops its owned process, then restores files before `RestoreSettings` checks for another running game. A user game started after the owned process exited can therefore receive file changes. Recheck the installation and all live game processes immediately before restoration and retain the journal if restoration is unsafe. This guard must also apply to explicit recovery.
- **P2 — Publication audit must inspect the published blobs.** `infra/public_tree.py` uses tracked filenames but reads working-tree content. Sanitized unstaged content can hide unsafe staged content. Inspect the index or final commit blobs selected for publication. Normalize forbidden extensions case-insensitively and reject private configuration, captures and compiled material independently of `.gitignore`. Test staged/worktree divergence and uppercase file extensions.

The initial findings above are retained. Candidate propagation, installation-wide persistent/process locking, pre-restoration running-game checks and staged-blob publication scanning were subsequently corrected and received rejection/recovery regressions. Built-in fresh Console supported/immediate and History bounded/transition collectors now exist. Console still needs a nominated save. Fresh History bounded v2 FAILed after two gender changes: allocation reset, but the first fresh physical purchase did not change native stats. An independent delayed diagnostic click also failed and the UI displayed zero physical points. The code cause remains unresolved; this is not dismissed as automation loss. Library predicates now require native permission, a distinct owned Shadow, cleanup and exact selected BSP. Fresh Protean, Frenzy, Subtitle and Background collector adapters remain unfinished and need nominated saves; those scenarios stay BLOCKED. Audit rejection checks now require both Griffith contacts, actual ground observation, each end/load/map state, exact resource selection and actual Protean active-load/map cleanup. Generic success labels are insufficient. This review does not claim complete fresh gameplay coverage.

## Review by release family

| Family | Required behavior and retained coverage | Remaining boundary and next regression |
| --- | --- | --- |
| **Console Pause Fix 1.0.1** | Release only console-owned pause; preserve ordinary/script pause and prior menu; restore world, audio and input separately. `plugin/console_pause.c`, `tests/native_harness.c` and `tests/exact_harness.c` cover ownership, queue order, recursion, ABI, context and installation failures. Historical gameplay observations cover the measured external readiness wait. | Immediate input is not certified. Keep its first result, actual close/input timing, native button receipt and signed movement/camera observations. Generic world resume is insufficient. Also verify memory protection and cache-flush failure paths described below. |
| **Protean Improved Core 1.2.2 and models** | One owned Shadow and no bonus accumulation; correct behavior for either state ending first; safe load/map cleanup; independent filter/RedVision handling. Exact harness and emitted-code tests exercise the final native helpers. `models/test_release_models.py` and preserved model regressions check resource bytes, combat links, metadata, donors and corrupt inputs. | Original combos 1.2.0 and Four-hit 1.2.1 are current alternatives. Preserve all six model archives. Four-hit hit windows, normal follow-up input, termination, interruption/restart, actual Tiger route and visual hand transitions must not inherit static acceptance. Resolve actor-model sequences instead of copying sequence numbers between models. Add native resource-selection and event/weapon/sequence correlation. A saved-active P4 scenario uses a task save; active-load testing does not prove creation of a save with both P5 and Frenzy active. |
| **Frenzy Fixes 1.2.1** | Keep BSP permission changes separate from native Werewolf collision correction. `plugin/griffith_frenzy_werewolf_fix.c` retains TraceRay and SetGround corrections and owner/map/serial guards; exact harness covers forwarding, scope and lifecycle while verifying stock SetOrigin remains untouched. | Griffith damaging approach and ordinary/P5 contexts do not certify literal hull overlap or the delivered Library BSP. The release record reports a different installed Library resource. Test the exact delivered BSP or explicitly report `BLOCKED`. Add resource resolution, native permission/Shadow/cleanup predicates, dynamic hook installation failures and cache-flush failures. |
| **Subtitle Pause Fix 1.3.0** | Pause/on/off/repeat, radio/TV transitions, saved-on/load return and an unaccelerated radio loop must preserve correlated audio and captions. Retained clock emulation, dispatcher/native harnesses, clean checks and process-audio collectors cover distinct layers. | The original equal-split sentence onset and ordinary audio pipeline offset remain limitations. Fresh tests must retain caption intervals and independently correlated process PCM, not only a checksum string or collector-selected score. Adapt collectors into the common runner without requiring removed plugin logs or private clock structures. Do not treat the recorded loop length as a universal asset property. |
| **Cutscene Subtitle Background Fix 1.0.0** | Skip only native fill/border during the cinematic fade, retaining ordinary visibility handling and text. `plugin/subtitle_background.c` uses one guarded branch change, with no timing state or trampoline. Retained relocated-reference/native tests cover signature uniqueness and install/rollback failure paths. | Add runnable fresh observation for two actual cinematic contexts and ordinary dialogue, comparing text, placement and wrapping. An offline draw-block check does not certify visual behavior through load/map. Keep supported client identity explicit. |
| **History Stat Reset Fix 1.5.1** | The current requirement resets purchased allocation and History bonus on gender change, returns the full spendable pool, rejects overspending, and preserves new purchases through Base/Sheet and Accept. `gender_regression.py`, native getters and exact verification retain these workflows, one-shot ownership, call order and transactional installation. | Allocation-preserving drafts are superseded and must not supply expectations. Full native resets consume entity slots; bounded correctness does not establish unlimited endurance. Observe a short declared reset sequence and preserve the inherited resource limitation separately. Existing coordinate input requires a supported geometry and must block without changing video settings. |

Paths in this table are relative to the corresponding `mods/<family>` directory. Existing gameplay material remains historical until a fresh collector, independent audit and preservation result bind it to the exact tested artifact.

## Native OS failure review

The following are confirmed source-control-flow observations. Exact-binary cache-flush fault probes subsequently confirmed FAIL for Console (four refusals), Protean (seven) and Frenzy (two): each leaves a hook installed after injected cache-flush refusal. These run in isolated private/synthetic fixture pages without game launch or release modification. Run `./RunTests.ps1 -Suite faults -Config local.json` to reproduce all three. They are visible failing review regressions; passing retained CI/offline coverage does not imply they pass. No new real-game failure is claimed.

- **Protean:** `write_memory` ignores both `FlushInstructionCache` and restoration `VirtualProtect` results and returns success after the initial protection change. Its exact harness explicitly accepts some restore-protection failures as a valid installation. This does not prove the original page protection or executable-cache state was restored. Fault tests should check byte ownership, original protection, helper lifetime and final installation state.
- **Frenzy:** `write_memory` has the same ignored cache-flush/protection-restoration results. Stub creation also ignores its cache flush. Existing exact tests primarily inject the first protection failure; add faults after writes and during dynamically installed TraceRay/SetGround hooks. Do not simply change the return value: once bytes reference a helper, failure handling must retain that helper until a verified rollback.
- **Console:** `write_bytes` ignores cache-flush failure. If its final protection restoration fails, rollback obtains the now-writable protection as its new `old` value and can restore original bytes while leaving the page writable. The current rollback tests compare bytes, not original protection. Add original-protection tracking and `VirtualQuery` assertions. Include cache-flush failure for generated trampolines and patched sites.
- **History and Subtitle:** installation tracks changed hooks, retries rollback and keeps callable helper memory when restoration cannot be certified. These are necessary safeguards. Add targeted tests for the occupied-after-protection branch: the hook has not been marked changed, but protection restoration can still fail. Byte rollback alone must not imply all OS state is restored.
- **Background:** installation rechecks ownership and independently attempts flush/protection recovery after restoring bytes. Preserve this behavior and test repeated OS failures, rather than generalizing another family's installer without equivalent guarantees.

Any resulting code correction produces a new candidate identity. Finalize first, run technical and relevant gameplay tests on those exact bytes, and do not rebuild or strip them afterward. The unchanged accepted release remains the reference until replacement is authorized and validated.

## Provenance, packaging and future acceptance

The original Subtitle capsule includes MIT `LICENSE` and `NOTICE`. The original Frenzy and History capsules include `LICENSE_STATUS.txt` stating that no standalone license grant was inferred. Their absence of a license is a historical fact, not proof of third-party authorship or permission to relicense third-party material. The owner's explicit MIT authorization applies to the verified original workspace sources and tests. Preserve the provenance map, original member hashes and transformations; retain any identified third-party conditions separately. Game assets and complete game modules are local inputs, outside the source-code license grant. Correct the old Subtitle notice's engine-only module description when documenting the current combined implementation.

Future acceptance gates should distinguish:

1. **CI:** own-source compilation, permitted synthetic fixtures, infrastructure fault tests, source/public-tree checks and explicit limitations; no gameplay acceptance.
2. **Offline:** exact clean artifact verification against local pinned modules and resources, corruption tests, package allowlists, safe paths and preserved release identity.
3. **Gameplay:** runnable native collectors, requirement-specific independent audits, exact installed/resolved resources, first-failure retention, finite timeouts and verified restoration.
4. **Export:** test each source capsule from an isolated extraction with no access to the original workspace. Require one `README.md`, required shared dependencies, no compiled tests/private evidence, and usable explicit local-input instructions. Gameplay archives contain necessary game-layout fixes plus one English manual `README.txt`; no installer, alternate README, checksum manifest or gameplay checklist.

Before cleanup, verify recoverable archives of unique internal material and run the relocated source tests. Delete only enumerated task-owned duplicates/temporary files after those checks. User backups, preserved original saves, existing evidence and excluded prototype material remain protected. A passing infrastructure test cannot substitute for this preservation check or for a missing gameplay scenario.

## Additional infrastructure findings and corrected behavior

Later recovery no longer treats any runtime output as owned merely because an
old PID was recorded. The live controller seals file hashes/timestamps and
settings immediately after stopping its own process; later recovery requires
those observations or unchanged originals. Newer user configuration/settings
are preserved and cause BLOCKED. Unknown runtime output still requires explicit
reconciliation. Scenario outcome and preservation outcome are recorded
separately, so restoration failure cannot erase a first behavioral FAIL.

Collectors and their descendants are confined to an owned Windows Job Object
with finite timeout and kill-on-close. The separately owned game outlives its
launcher and is stopped only by its recorded PID/creation time. Hanging
child/grandchild fixtures verify termination without stopping a separate
control process. Tests also exercise typed registry restoration in an isolated
new fixture key, never by overwriting game video preferences.

The History reader scans 8192 handle-table entries; this is not the allocator
capacity. Historical native exhaustion near 2001 occupied entries remains a
separate limitation. Bounded tests record observed growth, without declaring
every count below 8192 safe or promising unlimited reset endurance.

The first fresh History preparation failed because collector dependencies were
not propagated, and engine startup produced previously unregistered Python 2
caches. Recovery correctly stopped on unknown files. Those exact caches were
independently reconciled against source/header/time observations, archived and
removed before verified restoration. Dependencies are now preflighted and
each derived cache destination is declared before launch. A subsequent test
incorrectly equated a complete spendable pool with stock XP=9000; that failed
test is preserved and its assumption removed in scenario version 2. The actual
new-purchase failure remains FAIL. Rejection/purchase audits derive counts and
native costs from raw states rather than accepting a collector summary.

## Fresh gameplay status and reproduction

| Scenario | Collector | Fresh result / limitation | Command |
| --- | --- | --- | --- |
| Console supported | Built-in | Preparation failed before the first Console action after loading the verified archival nominee; first FAIL retained. Own plugin/save/CFG/caches restored; later config decision remains BLOCKED. Retained five-second evidence remains historical | `./RunTests.ps1 -Suite gameplay -Scenario console.supported` |
| Console immediate | Built-in | BLOCKED by unfinished supported-run recovery; immediate workflow did not start | `./RunTests.ps1 -Suite gameplay -Scenario console.immediate` |
| History bounded resets | Built-in (current v3) | FAIL: new physical purchase after two resets; exact release, observed slot growth and verified restoration | `./RunTests.ps1 -Suite gameplay -Scenario history.bounded_resets` |
| History transitions | Built-in | FAIL: first fresh purchase after actual bonus History/repeated selection and gender reset; preservation PASS. Later None/Accept portions were not reached | `./RunTests.ps1 -Suite gameplay -Scenario history.transitions` |
| Protean lifecycle/filter/fourhit | External contract; adapter incomplete | BLOCKED: fresh collector and nominated warehouse/claws saves absent | `./RunTests.ps1 -Suite gameplay -Mod protean` |
| Frenzy Library/Griffith | External contract; adapter incomplete | BLOCKED: fresh collectors and nominated distinct saves absent; Griffith cannot certify Library | `./RunTests.ps1 -Suite gameplay -Mod frenzy` |
| Subtitle radio | External contract; adapter incomplete | BLOCKED: fresh native/PCM collector and nominated radio save absent | `./RunTests.ps1 -Suite gameplay -Scenario subtitle.radio` |
| Background cinematics | External contract; adapter incomplete | BLOCKED: fresh cinematic/text observations and nominated save absent | `./RunTests.ps1 -Suite gameplay -Scenario background.cinematics` |

The repository and hosted CI are published. CI checks technical/source and
infrastructure coverage only. The new faults suite remains visibly failing on
the unchanged releases. No release version or acceptance has been advanced.


## Latest infrastructure and evidence changes

The latest History pool audit binds each attempted purchase to its exact category,
native before/after state, owned PID/start time, foreground, cursor target,
actual SendInput receipt and distinct action identity. Unchanged stats alone
cannot prove an exhausted-category rejection. Full rejection certification
requires an action-bound native UI command observer; that collector is still
missing and produces BLOCKED. Earlier fresh purchase failures remain FAIL.
History bounded scenario v3 and transitions v2 record these stricter receipts;
the retained actual game failures were collected with their earlier versions.

Console supported v2 explicitly separates preparation from the first Console
action. A lost-foreground guard before that boundary yields BLOCKED with the
first error and available foreground-owner readback preserved. After the
boundary, an unmet behavior remains FAIL. The original v1 run is retained
unchanged: it lost foreground before any Console action. There is no proof
of its cause or successful immediate-input behavior.

Process inspection now retains access-denied/null-start observations as
UNVERIFIED and blocks mutation, instead of crashing on null StartTime. A
historical parent PID is insufficient to terminate an unverified descendant.
Session journals are retained separately so starting another session cannot
overwrite the prior session's final intents and recovery history.

The current isolated infrastructure suite passes 73 tests, including actual
typed registry interruption/recovery in new owned fixture keys, uninspectable
process observations, explicit per-file decisions and partial recovery that
cannot release the installation lock. Console recovery verified owned cache
bytes, original source/header and creation times before removal. The original
installed plugin, task save and CFG were restored/removed as recorded; only
the later existing config.cfg is left untouched pending an operator choice.
