# Historical opt-in recipe: use the shared transactional session API for new runs.
[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('Snapshot','Launch','Stop','Restore','Audit')][string]$Action,
      [Parameter(Mandatory)][string]$WorkRoot, [string]$BackgroundPlugin='',
      [string]$Label='clean', [string]$Save='autosave', [string]$Probe='', [string]$Plugin='')
$ErrorActionPreference='Stop'
$game='LOCAL_GAME_ROOT_REQUIRED'
$work=[IO.Path]::GetFullPath($WorkRoot)
$backup=Join-Path $work 'originals'
if($Action -in @('Launch','Restore') -and (Test-Path -LiteralPath (Join-Path $work 'installation.json'))){throw 'Permanent installation completed; create a fresh work root rather than reusing this snapshot'}
function GamePath([string]$rel) {
    $p=[IO.Path]::GetFullPath((Join-Path $game $rel))
    if(-not $p.StartsWith($game+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Path escapes game'}
    $p
}
function NoGame {if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'Game already running; refuse launch/mutation'}}
function Video {
    if((whoami.exe).Trim() -ne 'LOCAL_LAUNCH_USER_REQUIRED'){throw 'Real user required'}
    foreach($sub in @('Settings','ResPatch')) {
        $key=Get-Item -LiteralPath ('HKCU:\Software\Troika\Vampire\'+$sub)
        foreach($name in $key.GetValueNames() | Sort-Object){[pscustomobject]@{Sub=$sub;Name=$name;Kind=$key.GetValueKind($name).ToString();Value=$key.GetValue($name)}}
    }
}
function Links {
    $shell=New-Object -ComObject WScript.Shell
    foreach($dir in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'))) {
        foreach($f in Get-ChildItem -LiteralPath $dir -Filter '*.lnk' -File){
            $l=$shell.CreateShortcut($f.FullName)
            if($l.TargetPath -match 'Vampire|Bloodlines|Loader'){[pscustomobject]@{Path=$f.FullName;Target=$l.TargetPath;Arguments=$l.Arguments;WorkingDirectory=$l.WorkingDirectory}}
        }
    }
}
$inventoryDirs=@('Unofficial_Patch\cfg','Vampire\cfg','Unofficial_Patch\save','Vampire\save','Bin\loader','Unofficial_Patch\resource','Unofficial_Patch\python')
if($Action -eq 'Snapshot'){
    NoGame
    $video=@(Video);$links=@(Links)
    if(Test-Path -LiteralPath $backup){throw 'Original snapshot exists'}
    New-Item -ItemType Directory -Path $backup | Out-Null
    $video | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $backup 'video.json') -Encoding UTF8
    $links | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $backup 'shortcuts.json') -Encoding UTF8
    whoami.exe | Set-Content -LiteralPath (Join-Path $backup 'user.txt')
    $paths=@('Bin\engine.dll','Vampire\dlls\vampire.dll','Vampire\cl_dlls\client.dll','Vampire\cl_dlls\GameUI.dll')
    foreach($dir in $inventoryDirs){if(Test-Path -LiteralPath (GamePath $dir)){$paths+=@(Get-ChildItem -LiteralPath (GamePath $dir) -File | ForEach-Object {$dir+'\'+$_.Name})}}
    foreach($dir in @('','Unofficial_Patch','Vampire')){$paths+=@(Get-ChildItem -LiteralPath (Join-Path $game $dir) -File | Where-Object Extension -In @('.log','.cfg','.txt','.exe','.inf') | ForEach-Object {if($dir){$dir+'\'+$_.Name}else{$_.Name}})}
    $paths+=@(Get-ChildItem -LiteralPath (GamePath 'Unofficial_Patch\python') -Recurse -File | ForEach-Object {$_.FullName.Substring($game.Length+1)})
    $paths+=@('Unofficial_Patch\models\character\shared\male\claws.mdl','Unofficial_Patch\models\character\shared\female\claws.mdl')
    $rows=@()
    foreach($rel in $paths | Sort-Object -Unique){
        $f=Get-Item -LiteralPath (GamePath $rel);$dest=Join-Path $backup $rel
        New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
        Copy-Item -LiteralPath $f.FullName -Destination $dest
        $hash=(Get-FileHash -LiteralPath $f.FullName).Hash
        if((Get-FileHash -LiteralPath $dest).Hash -ne $hash){throw 'Backup mismatch'}
        $rows+=[pscustomobject]@{Path=$rel;Hash=$hash;Size=$f.Length;Time=$f.LastWriteTimeUtc.ToString('o')}
    }
    $rows | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $backup 'files.json') -Encoding UTF8
    Write-Output "Preserved $($rows.Count) original files, real HKCU and shortcuts"
    exit
}
if($Label -notmatch '^[a-zA-Z0-9_]+$'){throw 'Unsafe label'}
$session=Join-Path $work ('sessions\'+$Label)
if($Action -eq 'Stop'){
    $owned=Get-Content -LiteralPath (Join-Path $session 'process.json') -Raw | ConvertFrom-Json
    $p=Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
    if($p){if($p.ProcessName -ne 'vampire' -or $p.StartTime.ToUniversalTime().Ticks -ne $owned.Ticks){throw 'Owned process identity mismatch'};Stop-Process -Id $p.Id;$p.WaitForExit(10000) | Out-Null}
    Write-Output "Closed owned PID $($owned.Id)";exit
}
NoGame
$rows=@(Get-Content -LiteralPath (Join-Path $backup 'files.json') -Raw | ConvertFrom-Json)
if($Action -eq 'Launch'){
    if($Save -notmatch '^[a-zA-Z0-9_]+$'){throw 'Unsafe save'}
    if(Test-Path -LiteralPath $session){throw 'Session already exists'}
    if((@(Video) | ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw).Trim()){throw 'Video originals differ'}
    foreach($row in $rows){if((Get-FileHash -LiteralPath (GamePath $row.Path)).Hash -ne $row.Hash){throw "Original changed before launch: $($row.Path)"}}
    New-Item -ItemType Directory -Path $session | Out-Null
    $pluginDest='';$pluginHash=''
    if($Plugin){
        $certificate=Get-Content -LiteralPath (Join-Path $work 'source\build\technical-verification.json') -Raw | ConvertFrom-Json
        $pluginHash=(Get-FileHash -LiteralPath $Plugin).Hash
        if($certificate.result -ne 'PASS' -or $certificate.hash -ne $pluginHash){throw 'Exact candidate technical certificate missing'}
        $pluginDest=GamePath 'Bin\loader\subtitle-pause-fix.vtm'
        $original=$rows | Where-Object Path -EQ 'Bin\loader\subtitle-pause-fix.vtm'
        if(-not $original -or (Get-FileHash -LiteralPath $pluginDest).Hash -ne $original.Hash){throw 'Verified preceding plugin mismatch'}
        $stage=$pluginDest+'.broadcast-sync-stage'
        if(Test-Path -LiteralPath $stage){throw 'Stage path occupied'}
        Copy-Item -LiteralPath $Plugin -Destination $stage
        if((Get-FileHash -LiteralPath $stage).Hash -ne $pluginHash){throw 'Stage mismatch'}
        [IO.File]::Replace($stage,$pluginDest,[NullString]::Value)
        if((Get-FileHash -LiteralPath $pluginDest).Hash -ne $pluginHash){throw 'Candidate replacement mismatch'}
    }
    $backgroundDest='';$backgroundHash=''
    if($BackgroundPlugin){
        $certificate=Get-Content -LiteralPath (Join-Path $work 'source\build\background-verification.json') -Raw | ConvertFrom-Json
        $backgroundHash=(Get-FileHash -LiteralPath $BackgroundPlugin).Hash
        if(-not $certificate.passed -or $certificate.plugin_hash -ne $backgroundHash){throw 'Exact background technical certificate missing'}
        $backgroundDest=GamePath 'Bin\loader\cutscene-subtitle-background-fix.vtm'
        $original=$rows | Where-Object Path -EQ 'Bin\loader\cutscene-subtitle-background-fix.vtm'
        if(-not $original -or (Get-FileHash -LiteralPath $backgroundDest).Hash -ne $original.Hash){throw 'Background preceding plugin mismatch'}
        Copy-Item -LiteralPath $BackgroundPlugin -Destination ($backgroundDest+'.clean-stage')
        if((Get-FileHash -LiteralPath ($backgroundDest+'.clean-stage')).Hash -ne $backgroundHash){throw 'Background stage mismatch'}
        [IO.File]::Replace($backgroundDest+'.clean-stage',$backgroundDest,[NullString]::Value)
    }
    foreach($logName in @('subtitle-pause-plugin.log','cutscene-subtitle-background-fix.log')){
        $logPath=GamePath $logName
        if(Test-Path -LiteralPath $logPath){
            $original=$rows | Where-Object Path -EQ $logName
            if(-not $original -or (Get-FileHash -LiteralPath $logPath).Hash -ne $original.Hash -or
                (Get-FileHash -LiteralPath (Join-Path $backup $logName)).Hash -ne $original.Hash){throw 'Log preservation mismatch'}
            Remove-Item -LiteralPath $logPath
        }
    }
    $args=@('-game','Unofficial_Patch','-dev','-novid','-console','+load',$Save)
    $probeDest=''
    if($Probe){
        $name=Split-Path $Probe -Leaf
        if($name -notmatch '^broadcast_sync_[a-z0-9_]+\.cfg$'){throw 'Unsafe probe filename'}
        $probeDest=GamePath ('Unofficial_Patch\cfg\'+$name)
        if(Test-Path -LiteralPath $probeDest){throw 'Probe destination occupied'}
        Copy-Item -LiteralPath $Probe -Destination $probeDest
        if((Get-FileHash -LiteralPath $probeDest).Hash -ne (Get-FileHash -LiteralPath $Probe).Hash){throw 'Probe mismatch'}
        $args+=@('+exec',$name)
    }
    [pscustomobject]@{Save=$Save;Arguments=$args;Probe=$probeDest;ProbeHash=$(if($Probe){(Get-FileHash -LiteralPath $Probe).Hash});Plugin=$pluginDest;PluginHash=$pluginHash;BackgroundPlugin=$backgroundDest;BackgroundHash=$backgroundHash;StartedUtc=[datetime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $session 'launch.json') -Encoding UTF8
    $p=Start-Process -FilePath (GamePath 'Vampire.exe') -WorkingDirectory $game -ArgumentList $args -WindowStyle Hidden -PassThru
    [pscustomobject]@{Id=$p.Id;Ticks=$p.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $session 'process.json') -Encoding UTF8
    Write-Output "Started owned PID=$($p.Id) save=$Save";exit
}
if($Action -eq 'Restore'){
    $launch=Get-Content -LiteralPath (Join-Path $session 'launch.json') -Raw | ConvertFrom-Json
    $owned=Get-Content -LiteralPath (Join-Path $session 'process.json') -Raw | ConvertFrom-Json
    $archive=Join-Path $session 'after-tests'
    foreach($row in $rows){
        $p=GamePath $row.Path
        if(Test-Path -LiteralPath $p){
            if((Get-FileHash -LiteralPath $p).Hash -eq $row.Hash){continue}
            $testReplacement=$row.Path -eq 'Bin\loader\subtitle-pause-fix.vtm' -and $launch.Plugin -eq $p -and (Get-FileHash -LiteralPath $p).Hash -eq $launch.PluginHash
            $testReplacement=$testReplacement -or ($row.Path -eq 'Bin\loader\cutscene-subtitle-background-fix.vtm' -and $launch.BackgroundPlugin -eq $p -and (Get-FileHash -LiteralPath $p).Hash -eq $launch.BackgroundHash)
            $mutable=$row.Path -like '*\cfg\*' -or $row.Path -like '*\save\*' -or $row.Path -like '*\python\*.pyc' -or $row.Path -like '*.log' -or $testReplacement
            if(-not $mutable){throw "Protected file changed: $($row.Path)"}
            $dest=Join-Path $archive $row.Path;New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
            Copy-Item -LiteralPath $p -Destination $dest
            if((Get-FileHash -LiteralPath $p).Hash -ne (Get-FileHash -LiteralPath $dest).Hash){throw 'Evidence archive mismatch'}
        }
        $src=Join-Path $backup $row.Path
        if((Get-FileHash -LiteralPath $src).Hash -ne $row.Hash){throw 'Backup damaged'}
        Copy-Item -LiteralPath $src -Destination $p -Force
        (Get-Item -LiteralPath $p).LastWriteTimeUtc=([datetime]$row.Time).ToUniversalTime()
    }
    foreach($dir in $inventoryDirs){
        if(-not(Test-Path -LiteralPath (GamePath $dir))){continue}
        foreach($f in Get-ChildItem -LiteralPath (GamePath $dir) -File -Recurse:($dir -like '*\python')){
            $rel=$f.FullName.Substring($game.Length+1)
            if($rows | Where-Object Path -EQ $rel){continue}
            $taskProbe=$launch.Probe -and $f.FullName -eq $launch.Probe -and (Get-FileHash -LiteralPath $f.FullName).Hash -eq $launch.ProbeHash
            # Engine autosave rotation renames old saves and retains their old
            # creation time. Attribute an extra rotation slot only by an exact
            # hash match to a preserved original save in this same directory.
            $rotatedSave=$false
            if($dir -like '*\save' -and $f.Name -match '^autosave[0-9]+\.sav$'){
                $extraHash=(Get-FileHash -LiteralPath $f.FullName).Hash
                $rotatedSave=[bool]($rows | Where-Object { $_.Path -like ($dir+'\autosave*.sav') -and $_.Hash -eq $extraHash })
            }
            $newSave=$dir -like '*\save' -and ($f.CreationTimeUtc.Ticks -ge $owned.Ticks -or $rotatedSave) -and $f.Extension -match '^\.(sav|HL[123])$'
            $newCache=$dir -like '*\python' -and $f.CreationTimeUtc.Ticks -ge $owned.Ticks -and $f.Extension -eq '.pyc'
            $testPlugin=$launch.Plugin -and $f.FullName -eq $launch.Plugin -and (Get-FileHash -LiteralPath $f.FullName).Hash -eq $launch.PluginHash
            $testPlugin=$testPlugin -or ($launch.BackgroundPlugin -and $f.FullName -eq $launch.BackgroundPlugin -and (Get-FileHash -LiteralPath $f.FullName).Hash -eq $launch.BackgroundHash)
            if(-not($taskProbe -or $newSave -or $newCache -or $testPlugin)){throw "Unknown inventory addition: $rel"}
            $dest=Join-Path $archive $rel;New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
            Copy-Item -LiteralPath $f.FullName -Destination $dest
            if((Get-FileHash -LiteralPath $f.FullName).Hash -ne (Get-FileHash -LiteralPath $dest).Hash){throw 'New file archive mismatch'}
            $resolved=[IO.Path]::GetFullPath($f.FullName)
            if(-not $resolved.StartsWith($game+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Removal escaped game'}
            Remove-Item -LiteralPath $resolved
        }
    }
    $log=GamePath 'cutscene-subtitle-background-fix.log'
    if($launch.Plugin -and (Test-Path -LiteralPath $log) -and -not($rows | Where-Object Path -EQ 'cutscene-subtitle-background-fix.log')){
        $f=Get-Item -LiteralPath $log
        if($f.CreationTimeUtc.Ticks -lt $owned.Ticks){throw 'Unexpected existing plugin log'}
        $dest=Join-Path $archive 'cutscene-subtitle-background-fix.log'
        Copy-Item -LiteralPath $log -Destination $dest
        if((Get-FileHash -LiteralPath $log).Hash -ne (Get-FileHash -LiteralPath $dest).Hash){throw 'Plugin log archive mismatch'}
        Remove-Item -LiteralPath $log
    }
}
foreach($row in $rows){
    $expected=$row.Hash
    if($Action -eq 'Audit' -and $Plugin -and $row.Path -eq 'Bin\loader\subtitle-pause-fix.vtm'){
        $tech=Get-Content -LiteralPath (Join-Path $work 'source\build\technical-verification.json') -Raw | ConvertFrom-Json
        $play=Get-Content -LiteralPath (Join-Path $work 'gameplay-verification.json') -Raw | ConvertFrom-Json
        $expected=(Get-FileHash -LiteralPath $Plugin).Hash
        if($tech.result -ne 'PASS' -or $play.result -ne 'PASS' -or $tech.hash -ne $expected -or $play.binary_sha256 -ne $expected){throw 'Passing exact installed candidate required'}
    }
    if((Get-FileHash -LiteralPath (GamePath $row.Path)).Hash -ne $expected){throw "Audit mismatch: $($row.Path)"}
    if($row.Path -like '*\save\*' -and (Get-Item -LiteralPath (GamePath $row.Path)).LastWriteTimeUtc.Ticks -ne ([datetime]$row.Time).ToUniversalTime().Ticks){throw 'Save timestamp differs'}
}
if($Action -eq 'Audit'){
    foreach($dir in $inventoryDirs){
        if(-not(Test-Path -LiteralPath (GamePath $dir))){continue}
        foreach($f in Get-ChildItem -LiteralPath (GamePath $dir) -File -Recurse:($dir -like '*\python')){
            $rel=$f.FullName.Substring($game.Length+1)
            if(-not($rows | Where-Object Path -EQ $rel)){throw "Unknown final inventory addition: $rel"}
        }
    }
}
if((@(Video) | ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw).Trim()){
    if($Action -ne 'Restore'){throw 'Video changed'}
    $originalVideo=@(Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw | ConvertFrom-Json)
    foreach($sub in @('Settings','ResPatch')){
        $key=Get-Item -LiteralPath ('HKCU:\Software\Troika\Vampire\'+$sub)
        foreach($name in $key.GetValueNames()){if(-not($originalVideo | Where-Object {$_.Sub -eq $sub -and $_.Name -eq $name})){$key.DeleteValue($name)}}
        foreach($v in $originalVideo | Where-Object Sub -EQ $sub){$key.SetValue($v.Name,$v.Value,[Microsoft.Win32.RegistryValueKind]::$($v.Kind))}
    }
    if((@(Video) | ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw).Trim()){throw 'Video restoration failed'}
}
if((@(Links) | ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'shortcuts.json') -Raw).Trim()){throw 'Shortcuts changed'}
Write-Output 'PASS original files, saves/timestamps, real HKCU and shortcuts'
