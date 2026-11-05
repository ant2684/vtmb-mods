[CmdletBinding()]
param([Parameter(Mandatory)][string]$GameRoot,[Parameter(Mandatory)][string]$LaunchJson,[Parameter(Mandatory)][string]$OutputJson)
$ErrorActionPreference='Stop'
if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'User game running'}
$launchData=Get-Content -LiteralPath $LaunchJson -Raw | ConvertFrom-Json
# Same ordinary shell launch used by the retained workbench game tests.
# No RunAs verb, compatibility overrides, credentials or video-mode arguments.
$ownedProcess=Start-Process -FilePath (Join-Path $GameRoot 'Vampire.exe') -WorkingDirectory $GameRoot -ArgumentList @($launchData.Arguments) -WindowStyle Hidden -PassThru
[pscustomobject]@{Id=$ownedProcess.Id;Ticks=$ownedProcess.StartTime.ToUniversalTime().Ticks;Launch='ordinary Start-Process'} | ConvertTo-Json -Compress | Set-Content -LiteralPath $OutputJson -Encoding utf8
