[CmdletBinding()]
param([Parameter(Mandatory)][string]$Zig,[Parameter(Mandatory)][string]$GameRoot,
 [Parameter(Mandatory)][string]$PayloadRoot,[string]$Python='python',[string]$Dependencies='')
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$output=Join-Path $taskRoot 'build/wolf_damage_exact.exe'
New-Item -ItemType Directory -Force -Path (Split-Path $output) | Out-Null
& $Python (Join-Path $taskRoot 'tools/verify_payload.py') $PayloadRoot
if($LASTEXITCODE -ne 0){throw 'Payload gate failed'}
& $Zig cc -target x86-windows-gnu -O2 -g0 -s -Wall -Wextra -Werror -o $output (Join-Path $taskRoot 'tests/wolf_damage_exact.c')
if($LASTEXITCODE -ne 0){throw 'Fixture compilation failed'}
& $output (Join-Path $PayloadRoot 'Bin/loader/griffith-wolf-native-damage.vtm') (Join-Path $GameRoot 'Vampire/dlls/vampire.dll') (Join-Path $GameRoot 'Bin/engine.dll')
if($LASTEXITCODE -ne 0){throw 'Exact VTM fixture failed'}
