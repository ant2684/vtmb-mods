# Historical opt-in recipe: use the shared transactional session API for new runs.
[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('Snapshot')][string]$Action,
      [Parameter(Mandatory)][string]$WorkRoot)
$ErrorActionPreference='Stop'
$game='LOCAL_GAME_ROOT_REQUIRED'
$work=[IO.Path]::GetFullPath($WorkRoot)
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

