[CmdletBinding()]
param(
    [string]$Zig = 'zig',
    [string]$Python = 'python',
    [switch]$Regenerate
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$output = Join-Path $root 'build\subtitle-pause-fix.vtm'
$env:ZIG_GLOBAL_CACHE_DIR = Join-Path $root 'build\zig-cache'
New-Item -ItemType Directory -Force -Path (Split-Path $output) | Out-Null

if ($Regenerate) {
    & $Python (Join-Path $root 'tools\generate_blobs.py')
    if ($LASTEXITCODE -ne 0) { throw 'Hook generation failed.' }
    Copy-Item (Join-Path $root 'tools\generated_clock.h') (Join-Path $root 'plugin\generated_clock.h') -Force
}

& $Zig cc -target x86-windows-gnu -shared -O2 -g0 -s -Wall -Wextra -Werror `
    -o $output (Join-Path $root 'plugin\subtitle_pause.c')
if ($LASTEXITCODE -ne 0) { throw 'Plug-in compilation failed.' }
& $Python (Join-Path $root 'tools\finalize_pe.py') $output
if ($LASTEXITCODE -ne 0) { throw 'Clean PE finalization failed.' }
Write-Host "Built: $output"
