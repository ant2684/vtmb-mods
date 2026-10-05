[CmdletBinding()]
param([string]$Zig = 'zig', [string]$Python = 'python', [string]$WindowsHeaders = '')

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$output = Join-Path $root 'build\history-stat-reset-fix.vtm'
New-Item -ItemType Directory -Force -Path (Split-Path $output) | Out-Null
if (!$WindowsHeaders) { $WindowsHeaders = Join-Path (Split-Path (Get-Command $Zig).Source) 'lib\libc\include\any-windows-any' }
& $Zig cc -target x86-windows-gnu -shared -nostdlib -isystem $WindowsHeaders '-Wl,--entry,DllMain@12' -O2 -g0 -s -Wall -Wextra -Werror -o $output (Join-Path $root 'plugin\history_stat_reset_fix.c') -lkernel32
if ($LASTEXITCODE -ne 0) { throw 'Plug-in compilation failed.' }
$importLibrary = Join-Path (Split-Path $output) 'history_stat_reset_fix.lib'
if (Test-Path $importLibrary) { Remove-Item -LiteralPath $importLibrary -Force }
Write-Host "Built: $output"
& $Python -B (Join-Path $root 'tools\finalize_pe.py') $output
if ($LASTEXITCODE -ne 0) { throw 'Clean PE finalization failed.' }
& $Zig cc -target x86-windows-gnu -O2 -g0 -s -Wall -Wextra -Werror -o (Join-Path $root 'build\load_clean.exe') (Join-Path $root 'tests\load_clean.c')
if ($LASTEXITCODE -ne 0) { throw 'External loader harness compilation failed.' }
