[CmdletBinding()]
param([Parameter(Mandatory)][string]$Zig, [string]$Python='python')
$ErrorActionPreference='Stop'
$out=Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $out 'zig-cache'
& $Zig cc -target x86-windows-gnu -shared -O2 -g0 -s -Wall -Wextra -Werror -o (Join-Path $out 'cutscene-subtitle-background-fix.vtm') (Join-Path $PSScriptRoot 'plugin/subtitle_background.c')
if($LASTEXITCODE){throw 'Plugin compilation failed'}
& $Python (Join-Path $PSScriptRoot 'tests/finalize_pe.py') (Join-Path $out 'cutscene-subtitle-background-fix.vtm')
if($LASTEXITCODE){throw 'Clean PE finalization failed'}
& $Zig cc -target x86-windows-gnu -O2 -Wall -Wextra -Werror -o (Join-Path $out 'load-clean.exe') (Join-Path $PSScriptRoot 'tests/load_clean.c')
if($LASTEXITCODE){throw 'Native load check compilation failed'}
& (Join-Path $out 'load-clean.exe') (Join-Path $out 'cutscene-subtitle-background-fix.vtm') loaded_client
if($LASTEXITCODE){throw 'Native clean plugin load failed'}
& $Zig cc -target x86-windows-gnu -O2 -Wall -Wextra -Werror -o (Join-Path $out 'native-harness.exe') (Join-Path $PSScriptRoot 'tests/native_harness.c')
if($LASTEXITCODE){throw 'Harness compilation failed'}
& (Join-Path $out 'native-harness.exe')
if($LASTEXITCODE){throw 'Harness failed'}
