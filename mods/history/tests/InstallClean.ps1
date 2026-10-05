# Historical opt-in recipe: use the shared transactional session API for new runs.
param([Parameter(Mandatory)][string]$WorkRoot,[Parameter(Mandatory)][string]$Candidate)
$ErrorActionPreference='Stop'
$work=[IO.Path]::GetFullPath($WorkRoot)
$cert=Get-Content (Join-Path $work 'gameplay-verification.json') -Raw|ConvertFrom-Json
$hash=(Get-FileHash -LiteralPath $Candidate).Hash
if($cert.result -ne 'PASS' -or $cert.hash -ne $hash -or $cert.scenarios.Count -ne 2 -or @($cert.scenarios|Where-Object {$_.result -ne 'PASS' -or $_.hash -ne $hash}).Count){throw 'Exact unique-scenario clean verification required'}
& "$PSScriptRoot/Session.ps1" -Action Audit -WorkRoot $work
$game='LOCAL_GAME_ROOT_REQUIRED'
$plugin=Join-Path $game 'Bin\loader\history-stat-reset-fix.vtm'
$backup=Join-Path $game ('Mod Backups\History Stat Reset Fix before correction '+[datetime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
New-Item -ItemType Directory -Path $backup|Out-Null
$oldHash=(Get-FileHash -LiteralPath $plugin).Hash
Copy-Item -LiteralPath $plugin -Destination (Join-Path $backup 'history-stat-reset-fix.vtm')
if((Get-FileHash (Join-Path $backup 'history-stat-reset-fix.vtm')).Hash -ne $oldHash){throw 'Backup mismatch'}
$log=Join-Path $game 'history-stat-reset-fix.log'
if(Test-Path -LiteralPath $log){
 Copy-Item -LiteralPath $log -Destination (Join-Path $backup 'history-stat-reset-fix.log')
 if((Get-FileHash $log).Hash -ne (Get-FileHash (Join-Path $backup 'history-stat-reset-fix.log')).Hash){throw 'Log archive mismatch'}
}
Copy-Item -LiteralPath $Candidate -Destination $plugin -Force
if((Get-FileHash -LiteralPath $plugin).Hash -ne $hash){throw 'Installation mismatch'}
if(Test-Path -LiteralPath $log){Remove-Item -LiteralPath $log}
$rows=Get-Content (Join-Path $work 'originals/files.json') -Raw|ConvertFrom-Json
foreach($r in $rows){if($r.Path -in @('Bin\loader\history-stat-reset-fix.vtm','history-stat-reset-fix.log')){continue};if((Get-FileHash -LiteralPath (Join-Path $game $r.Path)).Hash -ne $r.Hash){throw "Unrelated file changed: $($r.Path)"}}
foreach($r in $rows|Where-Object Path -Like '*\save\*'){
 if((Get-Item -LiteralPath (Join-Path $game $r.Path)).LastWriteTimeUtc.Ticks -ne ([datetime]$r.Time).ToUniversalTime().Ticks){throw 'Save timestamp changed'}
}
$video=@(foreach($sub in @('Settings','ResPatch')){
 $key=Get-Item -LiteralPath ('HKCU:\Software\Troika\Vampire\'+$sub)
 foreach($name in $key.GetValueNames()|Sort-Object){[pscustomobject]@{Sub=$sub;Name=$name;Kind=$key.GetValueKind($name).ToString();Value=$key.GetValue($name)}}
})
if(($video|ConvertTo-Json -Depth 8) -ne (Get-Content (Join-Path $work 'originals/video.json') -Raw).Trim()){throw 'Video changed'}
$shell=New-Object -ComObject WScript.Shell
$links=@(foreach($dir in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'))){foreach($f in Get-ChildItem -LiteralPath $dir -Filter '*.lnk' -File){$l=$shell.CreateShortcut($f.FullName);if($l.TargetPath -match 'Vampire|Bloodlines|Loader'){[pscustomobject]@{Path=$f.FullName;Target=$l.TargetPath;Arguments=$l.Arguments;WorkingDirectory=$l.WorkingDirectory}}}})
if(($links|ConvertTo-Json -Depth 8) -ne (Get-Content (Join-Path $work 'originals/shortcuts.json') -Raw).Trim()){throw 'Shortcuts changed'}
$report=[pscustomobject]@{result='PASS';hash=$hash;previous_hash=$oldHash;backup=$backup;installed_utc=[datetime]::UtcNow.ToString('o');preserved_files=$rows.Count;video_saves_shortcuts='PASS before install; only plugin and archived plugin log changed'}
$report|ConvertTo-Json|Set-Content (Join-Path $work 'installation.json') -Encoding UTF8
Write-Output "PASS installed exact tested binary; backup $backup"
