# Historical opt-in recipe: use the shared transactional session API for new runs.
[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('Snapshot','Launch','Stop','Restore','Audit')][string]$Action,
      [string]$Label='direct_a', [string]$Map='sp_endsequences_a', [string]$Probe='', [string]$Plugin='')
$ErrorActionPreference='Stop'
$game='LOCAL_GAME_ROOT_REQUIRED'
$work=Split-Path (Split-Path $PSScriptRoot)
$backup=Join-Path $work 'originals'
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
    if($Map -notin @('sp_endsequences_a','sp_endsequences_b')){throw 'Unreviewed map'}
    if(Test-Path -LiteralPath $session){throw 'Session already exists'}
    if((@(Video) | ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw).Trim()){throw 'Video originals differ'}
    foreach($row in $rows){if((Get-FileHash -LiteralPath (GamePath $row.Path)).Hash -ne $row.Hash){throw "Original changed before launch: $($row.Path)"}}
    New-Item -ItemType Directory -Path $session | Out-Null
    $pluginDest='';$pluginHash=''
    if($Plugin){
        $pluginDest=GamePath 'Bin\loader\cutscene-subtitle-background-fix.vtm'
        if(Test-Path -LiteralPath $pluginDest){throw 'Existing subtitle background plugin must be separately preserved'}
        $pluginHash=(Get-FileHash -LiteralPath $Plugin).Hash
        Copy-Item -LiteralPath $Plugin -Destination $pluginDest
        if((Get-FileHash -LiteralPath $pluginDest).Hash -ne $pluginHash){throw 'Plugin copy mismatch'}
    }
    $args=@('-game','Unofficial_Patch','-dev','-novid','-console','-condebug','+map',$Map)
    $probeDest=''
    if($Probe){
        $name=Split-Path $Probe -Leaf
        if($name -notmatch '^subtitle_bg_[a-z0-9_]+\.cfg$'){throw 'Unsafe probe filename'}
        $probeDest=GamePath ('Unofficial_Patch\cfg\'+$name)
        if(Test-Path -LiteralPath $probeDest){throw 'Probe destination occupied'}
        Copy-Item -LiteralPath $Probe -Destination $probeDest
        if((Get-FileHash -LiteralPath $probeDest).Hash -ne (Get-FileHash -LiteralPath $Probe).Hash){throw 'Probe mismatch'}
        $args+=@('+exec',$name)
    }
    [pscustomobject]@{Map=$Map;Arguments=$args;Probe=$probeDest;ProbeHash=$(if($Probe){(Get-FileHash -LiteralPath $Probe).Hash});Plugin=$pluginDest;PluginHash=$pluginHash;StartedUtc=[datetime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $session 'launch.json') -Encoding UTF8
    $p=Start-Process -FilePath (GamePath 'Vampire.exe') -WorkingDirectory $game -ArgumentList $args -WindowStyle Hidden -PassThru
    [pscustomobject]@{Id=$p.Id;Ticks=$p.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $session 'process.json') -Encoding UTF8
    Write-Output "Started owned PID=$($p.Id) map=$Map";exit
}
if($Action -eq 'Restore'){
    $launch=Get-Content -LiteralPath (Join-Path $session 'launch.json') -Raw | ConvertFrom-Json
    $owned=Get-Content -LiteralPath (Join-Path $session 'process.json') -Raw | ConvertFrom-Json
    $archive=Join-Path $session 'after-tests'
    foreach($row in $rows){
        $p=GamePath $row.Path
        if(Test-Path -LiteralPath $p){
            if((Get-FileHash -LiteralPath $p).Hash -eq $row.Hash){continue}
            $mutable=$row.Path -like '*\cfg\*' -or $row.Path -like '*\save\*' -or $row.Path -like '*\python\*.pyc' -or $row.Path -like '*.log'
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
    if((Get-FileHash -LiteralPath (GamePath $row.Path)).Hash -ne $row.Hash){throw "Audit mismatch: $($row.Path)"}
    if($row.Path -like '*\save\*' -and (Get-Item -LiteralPath (GamePath $row.Path)).LastWriteTimeUtc.Ticks -ne ([datetime]$row.Time).ToUniversalTime().Ticks){throw 'Save timestamp differs'}
}
if((@(Video) | ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'video.json') -Raw).Trim()){throw 'Video changed'}
if((@(Links) | ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $backup 'shortcuts.json') -Raw).Trim()){throw 'Shortcuts changed'}
Write-Output 'PASS original files, saves/timestamps, real HKCU and shortcuts'
