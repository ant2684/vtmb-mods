# Subtitle Pause Fix 1.3.0 maintenance source

Synchronizes native subtitle pause and radio activation/catch-up/loop caption coordinates while preserving television and other speech paths.

Based on the accepted 1.3.0 source capsule, with an unpublished startup correction. A fifth guarded callsite preserves the map's initial radio switch during Spawn, before Activate creates its stream. Later synchronization failures still remain muted. Public version numbers and existing release ZIPs are unchanged.

From the repository root:

```powershell
./RunTests.ps1 -Suite ci -Mod subtitle -Config local.json
./RunTests.ps1 -Suite offline -Mod subtitle -Config local.json
./RunTests.ps1 -Suite gameplay -Mod subtitle -List
```

Candidate verification uses `-Candidate <final-plugin>` with the offline suite. The native harness covers both original Spawn flag branches, the native switch and Activate callsite, nested startup scope and all 17 installation failure points. Its sound and base-Activate endpoints are bounded fixtures, not gameplay evidence.

`tests/startup_gameplay.py --config <local-config> --plugin <final-plugin> --audio-helper <capture_audio.exe> --output <new-evidence-folder>` runs the fresh-map and saved-state regression with file/settings restoration. Build the external audio helper with BuildDiagnostics.ps1 first. The optional `--baseline` flag requires the preceding plugin to reproduce its startup defect. Retain process PCM and native traces for an independent source-audio/caption audit; collector completion alone does not certify waveform synchronization.

Use pinned Zig 0.15.2/Python dependencies. Offline requires the frozen release directory and supported local game modules; missing inputs are BLOCKED. See the root docs for exact candidate verification, scenario limitations and recovery. Retained local Session/Install scripts are historical recipes; inspect and adapt them before use. Do not run an installation recipe merely to audit evidence.

Sources and technical checks are separate from the manual gameplay payload. Existing accepted ZIPs and source capsules remain byte-identical. Exact final bytes require renewed technical and relevant gameplay evidence after any behavior change.
