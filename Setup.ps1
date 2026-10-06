[CmdletBinding()]
param([string]$Python='python')
$ErrorActionPreference='Stop'
& $Python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 'Python 3.12 required')"
if($LASTEXITCODE){throw 'Install Python 3.12.10 (CI pin) or tested 3.12.14 before setup'}
& $Python -m venv (Join-Path $PSScriptRoot '.local/venv')
if($LASTEXITCODE){throw 'Python virtual environment failed'}
$venvPython=Join-Path $PSScriptRoot '.local/venv/Scripts/python.exe'
& $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if($LASTEXITCODE){throw 'Pinned Python dependencies failed'}
& $venvPython -m pip install --target (Join-Path $PSScriptRoot '.local/tools') ziglang==0.15.2
if($LASTEXITCODE){throw 'Pinned Zig installation failed'}
$configPath=Join-Path $PSScriptRoot 'local.json'
if(-not(Test-Path -LiteralPath $configPath)){
    $configuration=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'local.example.json') -Raw|ConvertFrom-Json
    $configuration.zig=Join-Path $PSScriptRoot '.local/tools/ziglang/zig.exe'
    $configuration|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $configPath -Encoding utf8
}
Write-Output 'Set zig in ignored local.json to .local/tools/ziglang/zig.exe. Use .local/venv/Scripts/python.exe for RunTests.'
