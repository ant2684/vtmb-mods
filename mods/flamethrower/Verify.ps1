[CmdletBinding()]
param([Parameter(Mandatory)][string]$Zig,[Parameter(Mandatory)][string]$GameRoot,
 [Parameter(Mandatory)][string]$Plugin,[string]$PayloadRoot='',
 [string]$Python='python',[string]$Dependencies='')
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$repoRoot=Split-Path (Split-Path $taskRoot)
$output=Join-Path $taskRoot 'build/flamethrower_exact.exe'
$certificate=Join-Path $taskRoot 'build/applied-patch.json'
New-Item -ItemType Directory -Force -Path (Split-Path $output) | Out-Null
$oldPythonPath=$env:PYTHONPATH
$oldZigCache=$env:ZIG_GLOBAL_CACHE_DIR
try {
 if($Dependencies){$env:PYTHONPATH=$Dependencies}
 $env:ZIG_GLOBAL_CACHE_DIR=Join-Path $taskRoot 'build/zig-cache'
 $cleanArgs=@('--plugin',$Plugin,'--exports','loaded_vampire','--source',(Join-Path $taskRoot 'plugin'))
 if($PayloadRoot){$cleanArgs+=@('--payload',$PayloadRoot)}
 & $Python -B (Join-Path $repoRoot 'infra/common/clean_payload.py') @cleanArgs
 if($LASTEXITCODE -ne 0){throw 'Payload gate failed'}
 & $Python -B (Join-Path $taskRoot 'tests/verify_flow.py') --server (Join-Path $GameRoot 'Vampire/dlls/vampire.dll') --identity-only
 if($LASTEXITCODE -ne 0){throw 'Unsupported native fixture'}
 & $Zig cc -target x86-windows-gnu -O2 -g0 -s -Wall -Wextra -Werror -o $output (Join-Path $taskRoot 'tests/exact.c')
 if($LASTEXITCODE -ne 0){throw 'Fixture compilation failed'}
 & $output $Plugin (Join-Path $GameRoot 'Vampire/dlls/vampire.dll') $certificate
 if($LASTEXITCODE -ne 0){throw 'Actual VTM fixture failed'}
 & $Python -B (Join-Path $taskRoot 'tests/verify_flow.py') --server (Join-Path $GameRoot 'Vampire/dlls/vampire.dll') --certificate $certificate --plugin $Plugin
 if($LASTEXITCODE -ne 0){throw 'Native floater flow failed'}
} finally {$env:PYTHONPATH=$oldPythonPath;$env:ZIG_GLOBAL_CACHE_DIR=$oldZigCache}
