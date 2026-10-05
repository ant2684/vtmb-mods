[CmdletBinding()]
param([string]$Python='python')
$ErrorActionPreference='Stop'
& $Python -m venv (Join-Path $PSScriptRoot '.local/venv')
if($LASTEXITCODE){throw 'Python virtual environment failed'}
$venvPython=Join-Path $PSScriptRoot '.local/venv/Scripts/python.exe'
& $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if($LASTEXITCODE){throw 'Pinned Python dependencies failed'}
& $venvPython -m pip install --target (Join-Path $PSScriptRoot '.local/tools') ziglang==0.15.2
if($LASTEXITCODE){throw 'Pinned Zig installation failed'}
Write-Output 'Set zig in ignored local.json to .local/tools/ziglang/zig.exe. Use .local/venv/Scripts/python.exe for RunTests.'
