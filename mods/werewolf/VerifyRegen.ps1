[CmdletBinding()]
param([Parameter(Mandatory)][string]$Zig,[Parameter(Mandatory)][string]$GameRoot,
 [Parameter(Mandatory)][string]$Plugin,[string]$Python='python',[string]$Dependencies='')
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$oldPythonPath=$env:PYTHONPATH
$oldZigCache=$env:ZIG_GLOBAL_CACHE_DIR
try {
 if($Dependencies){$env:PYTHONPATH=$Dependencies}
 $env:ZIG_GLOBAL_CACHE_DIR=Join-Path $taskRoot 'build/zig-cache'
 & $Python (Join-Path $taskRoot 'tests/verify_timer_api.py') (Join-Path $GameRoot 'Vampire/dlls/vampire.dll')
 if($LASTEXITCODE -ne 0){throw 'Stock timer/relay API qualification failed'}
 & $Python (Join-Path $taskRoot 'tests/verify_heal_flow.py') (Join-Path $GameRoot 'Vampire/dlls/vampire.dll')
 if($LASTEXITCODE -ne 0){throw 'Stock HealthHeal flow failed'}
 foreach($test in @('wolf_damage_exact','wolf_regen_exact')) {
  $output=Join-Path $taskRoot "build/$test.exe"
  & $Zig cc -target x86-windows-gnu -O2 -g0 -s -Wall -Wextra -Werror -o $output (Join-Path $taskRoot "tests/$test.c")
  if($LASTEXITCODE -ne 0){throw "Compilation failed: $test"}
  & $output $Plugin (Join-Path $GameRoot 'Vampire/dlls/vampire.dll') (Join-Path $GameRoot 'Bin/engine.dll')
  if($LASTEXITCODE -ne 0){throw "Exact VTM failed: $test"}
 }
} finally {$env:PYTHONPATH=$oldPythonPath;$env:ZIG_GLOBAL_CACHE_DIR=$oldZigCache}
