# Historical opt-in recipe: use the shared transactional session API for new runs.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$work=Split-Path (Split-Path $PSScriptRoot)
$gameRoot='LOCAL_GAME_ROOT_REQUIRED'
$relative='Bin\loader\cutscene-subtitle-background-fix.vtm'
$payload=Join-Path $work ('payload\'+$relative)
$built=Join-Path (Split-Path $PSScriptRoot) ('build\'+(Split-Path $relative -Leaf))
$destination=Join-Path $gameRoot $relative
if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'Game running; refuse installation'}
& (Join-Path $PSScriptRoot 'Session.ps1') -Action Audit
if(Test-Path -LiteralPath $destination){throw 'Unexpected existing destination; preserve it separately before replacement'}
if(Test-Path -LiteralPath (Join-Path $work 'installation.json')){throw 'Installation already recorded'}
$hash=(Get-FileHash -LiteralPath $built).Hash
if((Get-FileHash -LiteralPath $payload).Hash -ne $hash){throw 'Payload/build mismatch'}
$verification=Get-Content -LiteralPath (Join-Path (Split-Path $PSScriptRoot) 'build\verification.json') -Raw | ConvertFrom-Json
if(-not $verification.passed -or $verification.plugin_hash -ne $hash){throw 'Technical verification does not match build'}
$launch=Get-Content -LiteralPath (Join-Path $work 'sessions\final_a\launch.json') -Raw | ConvertFrom-Json
if($launch.PluginHash -ne $hash){throw 'Final in-game build differs'}
$observed=@(Get-Content -LiteralPath (Join-Path $work 'sessions\final_a\final\observations.jsonl') | ForEach-Object { $_ | ConvertFrom-Json })
if(-not($observed | Where-Object {$_.cinematic_fade -gt 0 -and $_.background_branch -eq 'e9bf00000090'})){throw 'Final in-game branch/cinematic evidence missing'}
$temporary=$destination+'.subtitle-background-task.tmp'
if(Test-Path -LiteralPath $temporary){throw 'Temporary destination occupied'}
Copy-Item -LiteralPath $payload -Destination $temporary
if((Get-FileHash -LiteralPath $temporary).Hash -ne $hash){throw 'Staged copy mismatch'}
if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'Game started during installation; refuse commit'}
Move-Item -LiteralPath $temporary -Destination $destination
if((Get-FileHash -LiteralPath $destination).Hash -ne $hash){throw 'Installed bytes mismatch'}
& (Join-Path $PSScriptRoot 'Session.ps1') -Action Audit
[pscustomobject]@{Path=$destination;Hash=$hash;Size=(Get-Item -LiteralPath $destination).Length;PreviousFile=$null;Originals='originals';FinalSession='final_a';InstalledUtc=[datetime]::UtcNow.ToString('o');Rollback='Close game and remove only Bin\loader\cutscene-subtitle-background-fix.vtm';OriginalAuditPassed=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work 'installation.json') -Encoding UTF8
Write-Output "Installed verified new plugin: $hash"
