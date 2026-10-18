# Subtitle Pause Fix 1.3.1 source

Synchronizes native subtitle pause and radio activation/catch-up/loop caption coordinates while preserving television and other speech paths.

Preserves the map's native radio state during Spawn and handles first activation after an early map-entry shutdown. A guarded client static-sound callsite records initial stream creation, so zero-position readiness keeps the broadcast epoch while later missing, replaced, ambiguous and unsupported streams remain muted. The gameplay payload contains only the clean loader plugin and manual README.

From the repository root:

```powershell
./RunTests.ps1 -Suite ci -Mod subtitle -Config local.json
./RunTests.ps1 -Suite offline -Mod subtitle -Config local.json
./RunTests.ps1 -Suite gameplay -Mod subtitle -List
```

Candidate verification uses `-Candidate <final-plugin>` with the offline suite. The native harness covers both original Spawn flag branches, the native switch and Activate callsite, nested startup scope and all 20 installation failure points, twelve-word static-sound cdecl forwarding/return/x87, early-off ordinary Use, zero-position readiness, stream identity and invalid-state refusal. Its sound and base-Activate endpoints are bounded fixtures, not gameplay evidence.

`tests/startup_gameplay.py --config <local-config> --plugin <final-plugin> --audio-helper <capture_audio.exe> --output <new-evidence-folder>` runs the fresh-map and saved-state regression with file/settings restoration. Build the external audio helper with BuildDiagnostics.ps1 first. The optional `--baseline` flag requires the preceding plugin to reproduce its startup defect. Retain process PCM and native traces for an independent source-audio/caption audit; collector completion alone does not certify waveform synchronization.

Use pinned Zig 0.15.2/Python dependencies. Offline requires the frozen release directory and supported local game modules; missing inputs are BLOCKED. See the root docs for exact candidate verification, scenario limitations and recovery. Retained local Session/Install scripts are historical recipes; inspect and adapt them before use. Do not run an installation recipe merely to audit evidence.

Sources and technical checks are separate from the manual gameplay payload. Existing accepted ZIPs and source capsules remain byte-identical. Exact final bytes require renewed technical and relevant gameplay evidence after any behavior change.

`tests/transition_gameplay.py --config <local-config> --save <tutorial-save> --plugin <final-plugin> --symbols <external-symbol-map> --capture <capture_audio.exe> --output <new-evidence-folder>` records the actual tutorial dialogue and map transition. The complete scenario runs automatically, skips NPC speech, selects a sole available response immediately and verifies both visible fourth choices. Numbered actions in the output folder's `control.json` are available only through `--interactive-debug` for diagnosis; retain the first Use result before further toggles. The external symbol map must match the exact final plugin hash. Native state, visible caption labels and process-only PCM are evidence inputs; a separate audit is required before claiming success. An apartment reload is a control, not a substitute for tutorial entry.
