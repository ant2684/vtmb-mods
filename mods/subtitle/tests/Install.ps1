# Historical opt-in recipe: use the shared transactional session API for new runs.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$work=Split-Path (Split-Path $PSScriptRoot)
$game='LOCAL_GAME_ROOT_REQUIRED'
$payload=Join-Path $work 'payload\Bin\loader\subtitle-pause-fix.vtm'
$dest=Join-Path $game 'Bin\loader\subtitle-pause-fix.vtm'
if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'Game must be closed; no process will be stopped'}
$tech=Get-Content (Join-Path $work 'source\build\technical-verification.json') -Raw | ConvertFrom-Json
$play=Get-Content (Join-Path $work 'gameplay-verification.json') -Raw | ConvertFrom-Json
$hash=(Get-FileHash -LiteralPath $payload).Hash
if($tech.result -ne 'PASS' -or $play.result -ne 'PASS' -or $tech.hash -ne $hash -or $play.binary_sha256 -ne $hash){throw 'Exact gameplay and technical gates required'}
& (Join-Path $PSScriptRoot 'Session.ps1') -Action Audit
if($LASTEXITCODE -ne 0){throw 'Original installation audit failed'}
$old='E957BF80DDEC76342D2D701C127F42C329D60A96439EBD7BCA949BD2FEDDB25C'
if((Get-FileHash -LiteralPath $dest).Hash -ne $old){throw 'Expected accepted 1.2.0 copy differs'}
$backupDir=Join-Path $game ('Mod Backups\Subtitle Pause Fix before radio synchronization '+[datetime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
$backup=Join-Path $backupDir 'subtitle-pause-fix.vtm'
$stage=$dest+'.broadcast-sync-stage'
foreach($p in @($backupDir,$stage)){
    $resolved=[IO.Path]::GetFullPath($p)
    if(-not $resolved.StartsWith($game+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Path escapes game installation'}
    if(Test-Path -LiteralPath $resolved){throw 'Backup or stage path occupied'}
}
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item -LiteralPath $dest -Destination $backup
if((Get-FileHash -LiteralPath $backup).Hash -ne $old){throw 'Backup verification failed'}
Copy-Item -LiteralPath $payload -Destination $stage
if((Get-FileHash -LiteralPath $stage).Hash -ne $hash){throw 'Stage verification failed'}
if((Get-FileHash -LiteralPath $dest).Hash -ne $old){throw 'Destination changed before replacement'}
[IO.File]::Replace($stage,$dest,[NullString]::Value)
if((Get-FileHash -LiteralPath $dest).Hash -ne $hash){throw 'Installed binary differs'}
& (Join-Path $PSScriptRoot 'Session.ps1') -Action Audit -Plugin $payload
if($LASTEXITCODE -ne 0){throw 'Final preservation audit failed'}
[pscustomobject]@{Result='PASS';InstalledUtc=[datetime]::UtcNow.ToString('o');Path=$dest;Hash=$hash;Size=(Get-Item -LiteralPath $dest).Length;Backup=$backup;BackupHash=$old;PreservedOriginalFiles=126;TechnicalReport='source/build/technical-verification.json';GameplayReport='gameplay-verification.json'} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $work 'installation.json') -Encoding utf8
Write-Output "Installed verified binary $hash; preceding 1.2.0 backup: $backup"
