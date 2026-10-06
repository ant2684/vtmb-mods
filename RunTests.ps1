[CmdletBinding()]
param(
    [ValidateSet('ci','offline','gameplay','historical','faults')][string]$Suite='offline',
    [string]$Config='', [string]$Mod='all', [string]$Candidate='',
    [string]$Python='', [string]$Output='', [switch]$List,
    [string]$Scenario=''
)
$ErrorActionPreference='Stop'
if(-not $Python){$venv=Join-Path $PSScriptRoot '.local/venv/Scripts/python.exe';$Python=if(Test-Path -LiteralPath $venv){$venv}else{'python'}}
if(-not $Config -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'local.json'))){$Config=Join-Path $PSScriptRoot 'local.json'}
$argsList=@('-B',(Join-Path $PSScriptRoot 'infra/runner.py'),'--suite',$Suite,'--mod',$Mod)
foreach($pair in @(@('--config',$Config),@('--candidate',$Candidate),@('--output',$Output),@('--scenario',$Scenario))) {
    if($pair[1]) { $argsList += $pair }
}
if($List){$argsList+='--list'}
& $Python @argsList
exit $LASTEXITCODE
