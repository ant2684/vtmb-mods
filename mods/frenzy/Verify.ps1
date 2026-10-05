[CmdletBinding()]
param([Parameter(Mandatory)][string]$Plugin,[Parameter(Mandatory)][string]$Zig,
 [Parameter(Mandatory)][string]$Game,[string]$Python='python',[string]$Dependencies='')
$ErrorActionPreference='Stop'
if((Get-FileHash -LiteralPath $Plugin).Hash -ne 'FD5FF2E0003FA712A73A5D92B88575B7920F7003789F4B7F27CA1B9FF539D38A'){throw 'Candidate differs from final release bytes'}
$oldPythonPath=$env:PYTHONPATH
try {
 if($Dependencies){$env:PYTHONPATH=$Dependencies}
 & $Python (Join-Path $PSScriptRoot 'tests/verify_exact.py') --plugin $Plugin --zig $Zig --game $Game
 if($LASTEXITCODE -ne 0){throw 'Exact-byte verification failed'}
} finally {$env:PYTHONPATH=$oldPythonPath}
