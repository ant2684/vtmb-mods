[CmdletBinding()]
param([Parameter(Mandatory)][string]$Zig,[string]$Python='python',[string]$Dependencies='')
$ErrorActionPreference='Stop'
$out=Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force $out | Out-Null
$priorPath=$env:PYTHONPATH
try {
 if($Dependencies){$env:PYTHONPATH=$Dependencies}
 $env:ZIG_GLOBAL_CACHE_DIR=Join-Path $out 'zig-cache'
 & $Zig cc -target x86-windows-gnu -shared -O2 -g0 -s -Wall -Wextra -Werror -nostdlib -Wl,--entry,DllMain@12 -lkernel32 -o (Join-Path $out 'container-stack-fix.vtm') (Join-Path $PSScriptRoot 'plugin/container_stack.c')
 if($LASTEXITCODE){throw 'Compilation failed'}
 & $Python -B (Join-Path $PSScriptRoot 'tools/finalize_pe.py') (Join-Path $out 'container-stack-fix.vtm')
 if($LASTEXITCODE){throw 'Finalization failed'}
} finally {$env:PYTHONPATH=$priorPath}
