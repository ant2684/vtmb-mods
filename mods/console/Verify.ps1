[CmdletBinding()]
param([Parameter(Mandatory)][string]$Plugin,[Parameter(Mandatory)][string]$Zig,
 [Parameter(Mandatory)][string]$Game,[string]$Python='python',[string]$Dependencies='')
$ErrorActionPreference='Stop'
if((Get-FileHash -LiteralPath $Plugin).Hash -ne '9919EBFC7A0661F26C3EA1F203139BEA39AB5C4E24252312072315965945B1FA'){throw 'Candidate differs from final release bytes'}
$oldPythonPath=$env:PYTHONPATH
try {
 if($Dependencies){$env:PYTHONPATH=$Dependencies}
 & $Python (Join-Path $PSScriptRoot 'tests/verify_exact.py') --plugin $Plugin --zig $Zig --game $Game
 if($LASTEXITCODE -ne 0){throw 'Exact-byte verification failed'}
} finally {$env:PYTHONPATH=$oldPythonPath}
