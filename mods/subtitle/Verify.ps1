[CmdletBinding()]
param([string]$Zig='zig', [string]$Python='python', [string]$Plugin='',
      [string]$Game='LOCAL_GAME_ROOT_REQUIRED')
$ErrorActionPreference='Stop'
if(-not $Plugin){$Plugin=Join-Path $PSScriptRoot 'build\subtitle-pause-fix.vtm'}
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $PSScriptRoot 'build\zig-cache'
& $Zig cc -target x86-windows-gnu -O2 -Wall -Wextra -Werror -o (Join-Path $PSScriptRoot 'tests\native_harness.exe') (Join-Path $PSScriptRoot 'tests\native_harness.c')
if($LASTEXITCODE -ne 0){throw 'Native harness compilation failed'}
& $Zig cc -target x86-windows-gnu -O2 -Wall -Wextra -Werror -o (Join-Path $PSScriptRoot 'tests\load_clean.exe') (Join-Path $PSScriptRoot 'tests\load_clean.c')
if($LASTEXITCODE -ne 0){throw 'Native load check compilation failed'}
& $Python (Join-Path $PSScriptRoot 'tests\verify.py') --game $Game --plugin $Plugin
if($LASTEXITCODE -ne 0){throw 'Technical verification failed'}
