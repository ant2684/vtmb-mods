# Historical opt-in recipe: use the shared transactional session API for new runs.
[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('Snapshot','Launch','Stop','Restore','Audit')][string]$Action,
 [string]$Label='console',[string]$SaveSource='', [string]$Probe='', [string]$Save='rc_console',[string]$StateRoot='',[Parameter(Mandatory)][string]$GameRoot,[Parameter(Mandatory)][string]$LaunchUser)
$ErrorActionPreference='Stop'
$tools=$PSScriptRoot
if(-not $StateRoot){$StateRoot=Join-Path $PSScriptRoot 'session-state'}
$work=[IO.Path]::GetFullPath($StateRoot)
New-Item -ItemType Directory -Force -Path $work|Out-Null
$game=[IO.Path]::GetFullPath($GameRoot).TrimEnd('\')
$backup=Join-Path $work 'originals'
$session=Join-Path $work ('sessions/'+$Label)
function GamePath([string]$rel){$p=[IO.Path]::GetFullPath((Join-Path $game $rel));if(-not $p.StartsWith($game+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Game path escaped'};$p}
function NoGame {if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'A user game is running; refuse mutation'}}
function Video {
 if((whoami.exe).Trim() -ne $LaunchUser){throw 'Real launch user required'}
 foreach($sub in @('Settings','ResPatch')){
  $path='HKCU:\Software\Troika\Vampire\'+$sub
  if(-not(Test-Path -LiteralPath $path)){[pscustomobject]@{Sub=$sub;Exists=$false;Values=@()};continue}
  $key=Get-Item -LiteralPath $path;$values=@(foreach($name in $key.GetValueNames()|Sort-Object){[pscustomobject]@{Name=$name;Kind=$key.GetValueKind($name).ToString();Value=$key.GetValue($name)}})
  [pscustomobject]@{Sub=$sub;Exists=$true;Values=$values}
 }
}
function Links {
 $shell=New-Object -ComObject WScript.Shell
 foreach($dir in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'))){foreach($f in Get-ChildItem -LiteralPath $dir -Filter '*.lnk' -File){$l=$shell.CreateShortcut($f.FullName);if($l.TargetPath -match 'Vampire|Bloodlines|Loader'){[pscustomobject]@{Path=$f.FullName;Target=$l.TargetPath;Arguments=$l.Arguments;WorkingDirectory=$l.WorkingDirectory}}}}
}
$dirs=@('Bin\loader','Unofficial_Patch\cfg','Vampire\cfg','Unofficial_Patch\save','Vampire\save','Unofficial_Patch\python','Unofficial_Patch\resource')
function Inventory {
 $files=@(foreach($dir in $dirs){if(Test-Path -LiteralPath (GamePath $dir)){Get-ChildItem -LiteralPath (GamePath $dir) -Recurse -File}})
 foreach($dir in @('','Unofficial_Patch','Vampire')){$files+=@(Get-ChildItem -LiteralPath (Join-Path $game $dir) -File | Where-Object Extension -In @('.cfg','.log','.txt','.exe','.inf'))}
 foreach($rel in @('Bin\engine.dll','Vampire\dlls\vampire.dll','Vampire\cl_dlls\client.dll','Vampire\cl_dlls\GameUI.dll','Unofficial_Patch\models\character\shared\male\claws.mdl','Unofficial_Patch\models\character\shared\female\claws.mdl','Unofficial_Patch\maps\sp_observatory_2.bsp','Unofficial_Patch\maps\la_library_1.bsp')){if(Test-Path -LiteralPath (GamePath $rel)){$files+=Get-Item -LiteralPath (GamePath $rel)}}
 $files | Sort-Object FullName -Unique
}
function Archive([string]$path,[string]$rel){$dest=Join-Path $session ('after-tests/'+$rel);New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null;Copy-Item -LiteralPath $path -Destination $dest;if((Get-FileHash -LiteralPath $path).Hash -ne (Get-FileHash -LiteralPath $dest).Hash){throw 'Evidence copy differs'}}
if($Label -notmatch '^[a-zA-Z0-9_]+$' -or $Save -notmatch '^[a-zA-Z0-9_]+$'){throw 'Unsafe label/save'}
if($Action -eq 'Snapshot'){
 NoGame;if(Test-Path -LiteralPath $backup){throw 'Fresh originals already exist'}
 New-Item -ItemType Directory -Path $backup | Out-Null
 @(Video)|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $backup 'video.json')
 @(Links)|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $backup 'shortcuts.json')
 $rows=@(foreach($f in Inventory){$rel=$f.FullName.Substring($game.Length+1);$dest=Join-Path $backup $rel;New-Item -ItemType Directory -Force -Path (Split-Path $dest)|Out-Null;Copy-Item -LiteralPath $f.FullName -Destination $dest;$hash=(Get-FileHash -LiteralPath $f.FullName).Hash;if((Get-FileHash -LiteralPath $dest).Hash -ne $hash){throw 'Backup differs'};[pscustomobject]@{Path=$rel;Hash=$hash;Size=$f.Length;Ticks=$f.LastWriteTimeUtc.Ticks}})
 $rows|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $backup 'files.json')
 Write-Output "Preserved fresh $($rows.Count) files, shortcut arguments and real video values/absence";exit
}
if($Action -eq 'Stop'){
 $owned=Get-Content -LiteralPath (Join-Path $session 'process.json') -Raw|ConvertFrom-Json;$p=Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
 if($p){if($p.ProcessName -ne 'vampire' -or $p.StartTime.ToUniversalTime().Ticks -ne $owned.Ticks){throw 'Own PID no longer matches'};Stop-Process -Id $p.Id;$p.WaitForExit(10000)|Out-Null};Write-Output "Closed only owned PID $($owned.Id)";exit
}
NoGame
$rows=@(Get-Content -LiteralPath (Join-Path $backup 'files.json') -Raw|ConvertFrom-Json)
$expectedVideo=(Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw).Trim()
if($Action -eq 'Launch'){
 foreach($row in $rows){if((Get-FileHash -LiteralPath (GamePath $row.Path)).Hash -ne $row.Hash){throw "Pre-launch original differs: $($row.Path)"}}
 if((@(Video)|ConvertTo-Json -Depth 8) -ne $expectedVideo){throw 'Pre-launch video differs'}
 if(Test-Path -LiteralPath $session){throw 'Session already exists'};New-Item -ItemType Directory -Path $session|Out-Null
 $payloads=@(@{Component='console';Name='console-pause-fix'})
 $installed=@()
 foreach($item in $payloads){$source=Join-Path $tools ('../../reference/'+$item.Name+'.vtm');$certificate=Get-Content -LiteralPath (Join-Path $tools '../../reference/technical-verification.json') -Raw|ConvertFrom-Json;$hash=(Get-FileHash -LiteralPath $source).Hash;if($certificate.result -ne 'PASS' -or $certificate.hash -ne $hash){throw 'Exact technical certificate absent'};$dest=GamePath ('Bin\loader\'+$item.Name+'.vtm');Copy-Item -LiteralPath $source -Destination $dest;if((Get-FileHash -LiteralPath $dest).Hash -ne $hash){throw 'Candidate copy differs'};$installed+=[pscustomobject]@{Path=$dest;Hash=$hash}}
 $taskFiles=@()
 $saveDest=GamePath ('Unofficial_Patch\save\'+$Save+'.sav');if(Test-Path -LiteralPath $saveDest){throw 'Temporary save destination occupied'}
 Copy-Item -LiteralPath $SaveSource -Destination $saveDest;$saveHash=(Get-FileHash -LiteralPath $SaveSource).Hash;if((Get-FileHash -LiteralPath $saveDest).Hash -ne $saveHash){throw 'Save copy differs'};$taskFiles+=[pscustomobject]@{Path=$saveDest;Hash=$saveHash}
 foreach($name in @('protean-improved-plugin.log','griffith-frenzy-werewolf-fix.log')){$p=GamePath $name;if(Test-Path -LiteralPath $p){Archive $p $name;Remove-Item -LiteralPath $p}}
 foreach($name in @('cleanup_probe.py','console_task_overlap.cfg','cleanup_aliases.cfg')){
  $src=Join-Path $tools $name;if(-not(Test-Path -LiteralPath $src)){continue};$rel=if($name.EndsWith('.py')){'Unofficial_Patch\python\'+$name}else{'Unofficial_Patch\cfg\'+$name};$dst=GamePath $rel;if(Test-Path -LiteralPath $dst){throw 'Task tool destination occupied'};Copy-Item -LiteralPath $src -Destination $dst
  if($name -eq 'cleanup_probe.py'){$body=[IO.File]::ReadAllText($dst);$out=(Join-Path $session 'probe.txt').Replace('\','/');$body=[regex]::Replace($body,"(?m)^OUT='[^']*'",("OUT='"+$out+"'"));[IO.File]::WriteAllText($dst,$body,[Text.Encoding]::ASCII)}
  $taskFiles+=[pscustomobject]@{Path=$dst;Hash=(Get-FileHash -LiteralPath $dst).Hash}
 }
 $args=@('-game','Unofficial_Patch','-dev','-novid','-console','+load',$Save)
 $launch=[pscustomobject]@{GameRoot=$game;Save=$Save;SaveHash=$saveHash;Arguments=$args;Candidates=$installed;TaskFiles=$taskFiles;StartedUtc=[datetime]::UtcNow.ToString('o')}
 $launch|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $session 'launch.json')
 $p=Start-Process -FilePath (GamePath 'Vampire.exe') -WorkingDirectory $game -ArgumentList $args -WindowStyle Hidden -PassThru
 [pscustomobject]@{Id=$p.Id;Ticks=$p.StartTime.ToUniversalTime().Ticks}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $session 'process.json');Write-Output "Started owned PID $($p.Id) loading verified $SaveHash";exit
}
if($Action -eq 'Restore'){
 $launch=Get-Content -LiteralPath (Join-Path $session 'launch.json') -Raw|ConvertFrom-Json;$owned=Get-Content -LiteralPath (Join-Path $session 'process.json') -Raw|ConvertFrom-Json
 foreach($f in Inventory){$rel=$f.FullName.Substring($game.Length+1);$row=$rows|Where-Object Path -EQ $rel;$hash=(Get-FileHash -LiteralPath $f.FullName).Hash
  if($row){if($hash -eq $row.Hash){continue};$candidate=$launch.Candidates|Where-Object {$_.Path -eq $f.FullName -and $_.Hash -eq $hash};$mutable=$rel -match '\\(cfg|save)\\|\.log$|\\python\\.*\.pyc$';if(-not($candidate -or $mutable)){throw "Protected original changed: $rel"};Archive $f.FullName $rel}
  else {$task=$launch.TaskFiles|Where-Object {$_.Path -eq $f.FullName -and $_.Hash -eq $hash};$runtime=$f.CreationTimeUtc.Ticks -ge $owned.Ticks -and ($rel -match '\\save\\.*\.(sav|HL[123])$|\\python\\.*\.pyc$|\.log$');$taskSave=$rel -match '\\save\\rc_[a-z0-9_]+\.(sav|HL[123])$';$rotation=$rel -match '\\save\\autosave[0-9]+\.sav$' -and [bool]($rows|Where-Object {$_.Path -match '\\save\\autosave.*\.sav$' -and $_.Hash -eq $hash});if(-not($task -or $runtime -or $taskSave -or $rotation)){throw "Unknown extra file: $rel"};Archive $f.FullName $rel;Remove-Item -LiteralPath (GamePath $rel)}
 }
 foreach($row in $rows){$dest=GamePath $row.Path;if(Test-Path -LiteralPath $dest){if((Get-FileHash -LiteralPath $dest).Hash -eq $row.Hash){continue}};$source=Join-Path $backup $row.Path;if((Get-FileHash -LiteralPath $source).Hash -ne $row.Hash){throw 'Original backup damaged'};Copy-Item -LiteralPath $source -Destination $dest -Force;(Get-Item -LiteralPath $dest).LastWriteTimeUtc=[datetime]::new([long]$row.Ticks,[DateTimeKind]::Utc)}
}
foreach($row in $rows){$p=GamePath $row.Path;if((Get-FileHash -LiteralPath $p).Hash -ne $row.Hash){throw "Restored hash differs: $($row.Path)"};if($row.Path -match '\\save\\' -and (Get-Item -LiteralPath $p).LastWriteTimeUtc.Ticks -ne $row.Ticks){throw 'Save timestamp changed'}}
foreach($f in Inventory){$rel=$f.FullName.Substring($game.Length+1);if(-not($rows|Where-Object Path -EQ $rel)){throw "Unknown final file: $rel"}}
if((@(Video)|ConvertTo-Json -Depth 8) -ne $expectedVideo){
 if($Action -ne 'Restore'){throw 'Video values changed'}
 $saved=Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw|ConvertFrom-Json
 foreach($sub in $saved){$path='HKCU:\Software\Troika\Vampire\'+$sub.Sub;if(-not $sub.Exists){if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path};continue};if(-not(Test-Path -LiteralPath $path)){New-Item -Path $path -Force|Out-Null};$key=Get-Item -LiteralPath $path;foreach($name in $key.GetValueNames()){if(-not($sub.Values|Where-Object Name -EQ $name)){$key.DeleteValue($name)}};foreach($value in $sub.Values){$key.SetValue($value.Name,$value.Value,[Microsoft.Win32.RegistryValueKind]::$($value.Kind))}}
 if((@(Video)|ConvertTo-Json -Depth 8) -ne $expectedVideo){throw 'Video restoration differs'}
}
if((@(Links)|ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'shortcuts.json') -Raw).Trim()){throw 'Shortcut arguments changed'}
@{Result='PASS';Action=$Action;Files=$rows.Count;VideoPreserved=$true;NoGame=$true}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $session 'preserved.json');Write-Output 'PASS fresh originals, saves/times, mods, video and shortcuts restored'
