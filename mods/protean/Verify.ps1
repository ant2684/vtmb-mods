[CmdletBinding()]
param([Parameter(Mandatory)][string]$Plugin,[Parameter(Mandatory)][string]$Zig,
 [Parameter(Mandatory)][string]$Game,[string]$Python='python',[string]$Dependencies='')
$ErrorActionPreference='Stop'
if((Get-FileHash -LiteralPath $Plugin).Hash -ne '14A68F6A1B61FBFD5F3A125AB59BA622B0670786693BDD05A7D13909A1199099'){throw 'Candidate differs from final release bytes'}
$oldPythonPath=$env:PYTHONPATH
try {
 if($Dependencies){$env:PYTHONPATH=$Dependencies}
 & $Python (Join-Path $PSScriptRoot 'tests/verify_exact.py') --plugin $Plugin --zig $Zig --game $Game
 if($LASTEXITCODE -ne 0){throw 'Exact-byte verification failed'}
} finally {$env:PYTHONPATH=$oldPythonPath}
