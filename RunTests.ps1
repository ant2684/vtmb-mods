[CmdletBinding()]
param(
    [ValidateSet('ci','offline','gameplay','historical','faults')][string]$Suite='offline',
    [string]$Config='', [string]$Mod='all', [string]$Candidate='',
    [string]$Python='python', [string]$Output='', [switch]$List,
    [string]$Scenario=''
)
$ErrorActionPreference='Stop'
$argsList=@('-B',(Join-Path $PSScriptRoot 'infra/runner.py'),'--suite',$Suite,'--mod',$Mod)
foreach($pair in @(@('--config',$Config),@('--candidate',$Candidate),@('--output',$Output),@('--scenario',$Scenario))) {
    if($pair[1]) { $argsList += $pair }
}
if($List){$argsList+='--list'}
& $Python @argsList
exit $LASTEXITCODE
