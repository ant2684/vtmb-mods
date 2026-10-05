# Historical opt-in recipe: use the shared transactional session API for new runs.
[CmdletBinding()]
param([ValidateSet('Launch','Stop','Restore','Audit')][string]$Action,
 [Parameter(Mandatory)][string]$WorkRoot,[string]$Label='baseline',
 [ValidateSet('installed','disabled','candidate')][string]$Variant='installed',
 [string]$Candidate='', [switch]$Diagnostic)
$ErrorActionPreference='Stop'
$game='LOCAL_GAME_ROOT_REQUIRED'
$work=[IO.Path]::GetFullPath($WorkRoot);$backup=Join-Path $work 'originals'
if($Action -ne 'Stop' -and (Test-Path -LiteralPath (Join-Path $work 'installation.json'))){throw 'Permanent install completed; take a new snapshot before further tests/restoration'}
$rows=@(Get-Content -LiteralPath (Join-Path $backup 'files.json') -Raw | ConvertFrom-Json)
if($Label -notmatch '^[a-zA-Z0-9_]+$'){throw 'Unsafe label'}
$session=Join-Path $work ('sessions\'+$Label)
$plugin='Bin\loader\history-stat-reset-fix.vtm'
function GamePath([string]$rel){$p=[IO.Path]::GetFullPath((Join-Path $game $rel));if(-not $p.StartsWith($game+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Path outside game'};$p}
function Video {
 if((whoami.exe).Trim() -ne 'LOCAL_LAUNCH_USER_REQUIRED'){throw 'Real-user context required'}
 foreach($sub in @('Settings','ResPatch')){$key=Get-Item -LiteralPath ('HKCU:\Software\Troika\Vampire\'+$sub);foreach($name in $key.GetValueNames() | Sort-Object){[pscustomobject]@{Sub=$sub;Name=$name;Kind=$key.GetValueKind($name).ToString();Value=$key.GetValue($name)}}}
}
function Links {
 $shell=New-Object -ComObject WScript.Shell
 foreach($dir in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'))){foreach($f in Get-ChildItem -LiteralPath $dir -Filter '*.lnk' -File){$l=$shell.CreateShortcut($f.FullName);if($l.TargetPath -match 'Vampire|Bloodlines|Loader'){[pscustomobject]@{Path=$f.FullName;Target=$l.TargetPath;Arguments=$l.Arguments;WorkingDirectory=$l.WorkingDirectory}}}}
}
function Archive([string]$path,[string]$rel){$dest=Join-Path $session ('after-tests\'+$rel);New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null;Copy-Item -LiteralPath $path -Destination $dest;if((Get-FileHash -LiteralPath $path).Hash -ne (Get-FileHash -LiteralPath $dest).Hash){throw 'Archive mismatch'}}
if($Action -eq 'Stop'){
 $owned=Get-Content -LiteralPath (Join-Path $session 'process.json') -Raw | ConvertFrom-Json;$p=Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
 if($p){if($p.ProcessName -ne 'vampire' -or $p.StartTime.ToUniversalTime().Ticks -ne $owned.Ticks){throw 'PID identity changed'};Stop-Process -Id $p.Id;$p.WaitForExit(10000)|Out-Null};Write-Output "Stopped owned PID $($owned.Id)";exit
}
if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'Existing game; refuse mutation'}
if($Action -eq 'Launch'){
 if(Test-Path -LiteralPath $session){throw 'Session exists'}
 if((@(Video)|ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw).Trim()){throw 'Video settings changed since snapshot'}
 foreach($row in $rows){if((Get-FileHash -LiteralPath (GamePath $row.Path)).Hash -ne $row.Hash){throw "Original changed: $($row.Path)"}}
 New-Item -ItemType Directory -Path $session -Force | Out-Null
 $original=$rows|Where-Object Path -EQ $plugin;$dest=GamePath $plugin
 if($Variant -eq 'disabled'){Remove-Item -LiteralPath $dest}
 if($Variant -eq 'candidate'){
  $hash=(Get-FileHash -LiteralPath $Candidate).Hash
  $cert=Get-Content -LiteralPath (Join-Path $work 'source\build\technical-verification.json') -Raw|ConvertFrom-Json
  if($cert.result -ne 'PASS' -or $cert.hash -ne $hash){throw 'Exact technical certificate required'}
  Copy-Item -LiteralPath $Candidate -Destination $dest -Force
  if((Get-FileHash -LiteralPath $dest).Hash -ne $hash){throw 'Candidate mismatch'}
  $log=GamePath 'history-stat-reset-fix.log';if(Test-Path -LiteralPath $log){Archive $log 'history-stat-reset-fix.log';Remove-Item -LiteralPath $log}
 }
 $args=@('-game','Unofficial_Patch','-dev','-novid','-console','+developer','0')
 if($Diagnostic){$args+=@('-condebug')}
 $probes=@()
 [pscustomobject]@{Variant=$Variant;Candidate=$Candidate;Probes=$probes;PluginHash=$(if(Test-Path -LiteralPath $dest){(Get-FileHash -LiteralPath $dest).Hash});Arguments=$args;StartedUtc=[datetime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $session 'launch.json') -Encoding UTF8
 $p=Start-Process -FilePath (GamePath 'Vampire.exe') -WorkingDirectory $game -ArgumentList $args -WindowStyle Hidden -PassThru
 [pscustomobject]@{Id=$p.Id;Ticks=$p.StartTime.ToUniversalTime().Ticks}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $session 'process.json') -Encoding UTF8
 Write-Output "Launched owned PID $($p.Id), $Variant, character creation";exit
}
if($Action -eq 'Restore'){
 $launch=Get-Content -LiteralPath (Join-Path $session 'launch.json') -Raw|ConvertFrom-Json
 $owned=Get-Content -LiteralPath (Join-Path $session 'process.json') -Raw|ConvertFrom-Json
 foreach($row in $rows){
  $p=GamePath $row.Path;$src=Join-Path $backup $row.Path
  if((Get-FileHash -LiteralPath $src).Hash -ne $row.Hash){throw 'Backup damaged'}
  if(Test-Path -LiteralPath $p){
   if((Get-FileHash -LiteralPath $p).Hash -eq $row.Hash){continue}
   $mutable=$row.Path -eq $plugin -or $row.Path -like '*\cfg\*' -or $row.Path -like '*\save\*' -or $row.Path -like '*\python\*.pyc' -or $row.Path -like '*.log'
   if(-not $mutable){throw "Protected file changed: $($row.Path)"};Archive $p $row.Path
  }else{if($row.Path -ne $plugin -and $row.Path -notlike '*.log'){throw "Original missing: $($row.Path)"}}
  Copy-Item -LiteralPath $src -Destination $p -Force;(Get-Item -LiteralPath $p).LastWriteTimeUtc=([datetime]$row.Time).ToUniversalTime()
 }
 foreach($dir in @('Unofficial_Patch\cfg','Vampire\cfg','Unofficial_Patch\save','Vampire\save','Unofficial_Patch\python','Bin\loader','','Unofficial_Patch','Vampire')){
  if(-not(Test-Path -LiteralPath (GamePath $dir))){continue}
  foreach($f in Get-ChildItem -LiteralPath (GamePath $dir) -File -Recurse:($dir -like '*\python')){
   if($dir -in @('','Unofficial_Patch','Vampire') -and $f.Extension -notin @('.log','.cfg','.txt','.exe','.inf')){continue}
   $rel=$f.FullName.Substring($game.Length+1);if($rows|Where-Object Path -EQ $rel){continue}
   $rotation=$f.Name -match '^autosave[0-9]+\.sav$' -and [bool]($rows|Where-Object {$_.Path -like '*\save\autosave*.sav' -and $_.Hash -eq (Get-FileHash -LiteralPath $f.FullName).Hash})
   $created=$f.CreationTimeUtc.Ticks -ge $owned.Ticks
   $known=$f.FullName -in $launch.Probes -or (($created -or $rotation) -and $f.Extension -in @('.sav','.HL1','.HL2','.HL3','.pyc','.log'))
   if(-not $known){throw "Unknown addition: $rel"};Archive $f.FullName $rel;Remove-Item -LiteralPath (GamePath $rel)
  }
 }
 if((@(Video)|ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw).Trim()){
  $orig=@(Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw|ConvertFrom-Json)
  foreach($sub in @('Settings','ResPatch')){$key=Get-Item -LiteralPath ('HKCU:\Software\Troika\Vampire\'+$sub);foreach($n in $key.GetValueNames()){if(-not($orig|Where-Object {$_.Sub -eq $sub -and $_.Name -eq $n})){$key.DeleteValue($n)}};foreach($v in $orig|Where-Object Sub -EQ $sub){$key.SetValue($v.Name,$v.Value,[Microsoft.Win32.RegistryValueKind]::$($v.Kind))}}
 }
}
foreach($row in $rows){if((Get-FileHash -LiteralPath (GamePath $row.Path)).Hash -ne $row.Hash){throw "Audit mismatch: $($row.Path)"};if($row.Path -like '*\save\*' -and (Get-Item -LiteralPath (GamePath $row.Path)).LastWriteTimeUtc.Ticks -ne ([datetime]$row.Time).ToUniversalTime().Ticks){throw 'Save timestamp changed'}}
if((@(Video)|ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw).Trim()){throw 'Video audit failed'}
if((@(Links)|ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'shortcuts.json') -Raw).Trim()){throw 'Shortcut audit failed'}
Write-Output 'PASS preserved original files, saves, real HKCU and shortcuts'

