# Historical opt-in recipe: use the shared transactional session API for new runs.
param([Parameter(Mandatory)][string]$WorkRoot,[Parameter(Mandatory)][string]$Candidate,[Parameter(Mandatory)][string]$Python)
$ErrorActionPreference='Stop'
# Separate automatic None/allocation and explicit History/bonus paths.
foreach($scenario in @(@('clean_transition','verify'),@('clean_history','history'))){
 $label=$scenario[0]
 & "$PSScriptRoot/Session.ps1" -Action Launch -WorkRoot $WorkRoot -Label $label -Variant candidate -Candidate $Candidate
 try{
  & $Python -B "$PSScriptRoot/gender_regression.py" (Join-Path $WorkRoot "sessions/$label") $scenario[1]
  if($LASTEXITCODE -ne 0){throw "Scenario failed: $label"}
  $game='LOCAL_GAME_ROOT_REQUIRED'
  if(Test-Path "$game/history-stat-reset-fix.log"){throw 'Unexpected plugin log'}
  if((Get-FileHash "$game/Bin/loader/history-stat-reset-fix.vtm").Hash -ne (Get-FileHash $Candidate).Hash){throw 'Exact tested bytes changed'}
 }finally{
  & "$PSScriptRoot/Session.ps1" -Action Stop -WorkRoot $WorkRoot -Label $label
  & "$PSScriptRoot/Session.ps1" -Action Restore -WorkRoot $WorkRoot -Label $label
 }
}
& $Python -B "$PSScriptRoot/audit_scenarios.py" $WorkRoot $Candidate (Join-Path $WorkRoot 'gameplay-verification.json')
if($LASTEXITCODE -ne 0){throw 'Scenario audit failed'}
