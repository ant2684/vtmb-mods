[CmdletBinding()]
param([Parameter(Mandatory)][string]$Zig,[string]$Python='python',[string]$Dependencies='')
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$repoRoot=Split-Path (Split-Path $taskRoot)
$output=Join-Path $taskRoot 'build/griffith-wolf-native-damage.vtm'
New-Item -ItemType Directory -Force -Path (Split-Path $output) | Out-Null
$oldPythonPath=$env:PYTHONPATH
$oldZigCache=$env:ZIG_GLOBAL_CACHE_DIR
try {
 if($Dependencies){$env:PYTHONPATH=$Dependencies}
 $env:ZIG_GLOBAL_CACHE_DIR=Join-Path $taskRoot 'build/zig-cache'
 & $Zig cc -target x86-windows-gnu -shared -O2 -g0 -s -Wall -Wextra -Werror -o $output (Join-Path $taskRoot 'plugin/wolf_damage_mode.c')
 if($LASTEXITCODE -ne 0){throw 'Compilation failed'}
 & $Python (Join-Path $repoRoot 'infra/common/finalize_pe.py') $output
 if($LASTEXITCODE -ne 0){throw 'PE finalization failed'}
} finally {$env:PYTHONPATH=$oldPythonPath;$env:ZIG_GLOBAL_CACHE_DIR=$oldZigCache}
Write-Output "Rebuilt candidate; requalify its exact bytes before use: $output"
