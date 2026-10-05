[CmdletBinding()]
param([Parameter(Mandatory)][string]$Zig,[string]$Python='python',[string]$Dependencies='')
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$output=Join-Path $root 'build/console-pause-fix.vtm'
New-Item -ItemType Directory -Force -Path (Split-Path $output) | Out-Null
$oldPythonPath=$env:PYTHONPATH
$oldZigCache=$env:ZIG_GLOBAL_CACHE_DIR
try {
 if($Dependencies){$env:PYTHONPATH=$Dependencies}
 $env:ZIG_GLOBAL_CACHE_DIR=Join-Path $root 'build/zig-cache'
 & $Zig cc -target x86-windows-gnu -shared -O2 -g0 -s -Wall -Wextra -Werror -o $output (Join-Path $root 'plugin/console_pause.c')
 if($LASTEXITCODE -ne 0){throw 'Compilation failed'}
 & $Python (Join-Path $root 'tools/finalize_pe.py') $output
 if($LASTEXITCODE -ne 0){throw 'PE finalization failed'}
 & $Python (Join-Path $root 'tests/clean_pe.py') $output --exports loaded_gameui --source (Join-Path $root 'plugin') --output (Join-Path $root 'build/clean-verification.json')
 if($LASTEXITCODE -ne 0){throw 'Cleanliness gate failed'}
} finally {$env:PYTHONPATH=$oldPythonPath;$env:ZIG_GLOBAL_CACHE_DIR=$oldZigCache}
Write-Output "Clean ordinary plugin: $output"
