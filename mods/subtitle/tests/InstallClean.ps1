# Historical opt-in recipe: use the shared transactional session API for new runs.
[CmdletBinding()]
param([Parameter(Mandatory)][string]$WorkRoot,
      [Parameter(Mandatory)][string]$RadioPlugin,
      [Parameter(Mandatory)][string]$BackgroundPlugin,
      [string]$Label='clean_verified')
$ErrorActionPreference='Stop'
$game='LOCAL_GAME_ROOT_REQUIRED'
if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'Game running; refuse replacement'}
if((whoami.exe).Trim() -ne 'LOCAL_LAUNCH_USER_REQUIRED'){throw 'Real user required'}
$work=[IO.Path]::GetFullPath($WorkRoot)
$rows=@(Get-Content -LiteralPath (Join-Path $work 'originals\files.json') -Raw | ConvertFrom-Json)
$session=Join-Path $work ('sessions\'+$Label)
$radioTech=Get-Content -LiteralPath (Join-Path $work 'source\build\technical-verification.json') -Raw | ConvertFrom-Json
$bgTech=Get-Content -LiteralPath (Join-Path $work 'source\build\background-verification.json') -Raw | ConvertFrom-Json
$radioPlay=Get-Content -LiteralPath (Join-Path $session 'radio-gameplay.json') -Raw | ConvertFrom-Json
$bgPlay=Get-Content -LiteralPath (Join-Path $session 'background-gameplay.json') -Raw | ConvertFrom-Json
$radioHash=(Get-FileHash -LiteralPath $RadioPlugin).Hash
$bgHash=(Get-FileHash -LiteralPath $BackgroundPlugin).Hash
function CheckSettings {
    $video=@(foreach($sub in @('Settings','ResPatch')){
        $key=Get-Item -LiteralPath ('HKCU:\Software\Troika\Vampire\'+$sub)
        foreach($name in $key.GetValueNames() | Sort-Object){[pscustomobject]@{Sub=$sub;Name=$name;Kind=$key.GetValueKind($name).ToString();Value=$key.GetValue($name)}}
    })
    if(($video | ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $work 'originals\video.json') -Raw).Trim()){throw 'Real HKCU changed'}
    $shell=New-Object -ComObject WScript.Shell
    $links=@(foreach($dir in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'))){
        foreach($f in Get-ChildItem -LiteralPath $dir -Filter '*.lnk' -File){
            $l=$shell.CreateShortcut($f.FullName)
            if($l.TargetPath -match 'Vampire|Bloodlines|Loader'){[pscustomobject]@{Path=$f.FullName;Target=$l.TargetPath;Arguments=$l.Arguments;WorkingDirectory=$l.WorkingDirectory}}
        }
    })
    if(($links | ConvertTo-Json -Depth 8) -ne (Get-Content -LiteralPath (Join-Path $work 'originals\shortcuts.json') -Raw).Trim()){throw 'Shortcuts changed'}
}
CheckSettings
if($radioTech.result -ne 'PASS' -or $radioPlay.result -ne 'PASS' -or $radioTech.hash -ne $radioHash -or $radioPlay.binary_sha256 -ne $radioHash){throw 'Exact clean radio technical/gameplay evidence missing'}
if(-not $bgTech.passed -or $bgPlay.result -ne 'PASS' -or $bgTech.plugin_hash -ne $bgHash -or $bgPlay.binary_sha256 -ne $bgHash){throw 'Exact clean backdrop technical/gameplay evidence missing'}
foreach($row in $rows){if((Get-FileHash -LiteralPath (Join-Path $game $row.Path)).Hash -ne $row.Hash){throw "Fresh original differs: $($row.Path)"}}
$stamp=[datetime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$backup=Join-Path $game ('Mod Backups\Subtitle fixes before diagnostic cleanup '+$stamp)
New-Item -ItemType Directory -Path $backup | Out-Null
$plugins=@(
    [pscustomobject]@{Name='subtitle-pause-fix.vtm';Source=$RadioPlugin;Hash=$radioHash},
    [pscustomobject]@{Name='cutscene-subtitle-background-fix.vtm';Source=$BackgroundPlugin;Hash=$bgHash}
)
$logs=@('subtitle-pause-plugin.log','cutscene-subtitle-background-fix.log')
foreach($p in $plugins){
    $path=Join-Path $game ('Bin\loader\'+$p.Name)
    Copy-Item -LiteralPath $path -Destination (Join-Path $backup $p.Name)
    if((Get-FileHash -LiteralPath $path).Hash -ne (Get-FileHash -LiteralPath (Join-Path $backup $p.Name)).Hash){throw 'Permanent plugin backup mismatch'}
}
foreach($name in $logs){
    $path=Join-Path $game $name
    if(Test-Path -LiteralPath $path){
        Copy-Item -LiteralPath $path -Destination (Join-Path $backup $name)
        if((Get-FileHash -LiteralPath $path).Hash -ne (Get-FileHash -LiteralPath (Join-Path $backup $name)).Hash){throw 'Permanent log archive mismatch'}
    }
}
$changed=@()
try {
    foreach($p in $plugins){
        $path=Join-Path $game ('Bin\loader\'+$p.Name);$stage=$path+'.clean-install-stage'
        if(Test-Path -LiteralPath $stage){throw 'Stage already occupied'}
        Copy-Item -LiteralPath $p.Source -Destination $stage
        if((Get-FileHash -LiteralPath $stage).Hash -ne $p.Hash){throw 'Stage differs'}
    }
    foreach($p in $plugins){
        $path=Join-Path $game ('Bin\loader\'+$p.Name)
        $original=$rows | Where-Object Path -EQ ('Bin\loader\'+$p.Name)
        if((Get-FileHash -LiteralPath $path).Hash -ne $original.Hash){throw 'Original changed before commit'}
        [IO.File]::Replace($path+'.clean-install-stage',$path,[NullString]::Value)
        $changed+=$p
        if((Get-FileHash -LiteralPath $path).Hash -ne $p.Hash){throw 'Installed bytes differ'}
    }
    foreach($name in $logs){if(Test-Path -LiteralPath (Join-Path $game $name)){Remove-Item -LiteralPath (Join-Path $game $name)}}
    foreach($row in $rows){
        if($logs -contains $row.Path){if(Test-Path -LiteralPath (Join-Path $game $row.Path)){throw 'Plugin log remains'};continue}
        $replacement=$plugins | Where-Object {('Bin\loader\'+$_.Name) -eq $row.Path}
        $expected=if($replacement){$replacement.Hash}else{$row.Hash}
        if((Get-FileHash -LiteralPath (Join-Path $game $row.Path)).Hash -ne $expected){throw "Final preservation mismatch: $($row.Path)"}
        if($row.Path -like '*\save\*' -and (Get-Item -LiteralPath (Join-Path $game $row.Path)).LastWriteTimeUtc.Ticks -ne ([datetime]$row.Time).ToUniversalTime().Ticks){throw 'Save timestamp differs'}
    }
    CheckSettings
    [pscustomobject]@{Result='PASS';Utc=[datetime]::UtcNow.ToString('o');Backup=$backup;RadioHash=$radioHash;BackgroundHash=$bgHash;OriginalFiles=$rows.Count;OnlyChanges='Two exact tested plugins, two archived plugin logs removed';PublicVersionAndZips='Unchanged'} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $work 'installation.json') -Encoding UTF8
    Write-Output "PASS exact clean plugins installed, logs archived/removed; backup=$backup"
} catch {
    foreach($p in $changed){Copy-Item -LiteralPath (Join-Path $backup $p.Name) -Destination (Join-Path $game ('Bin\loader\'+$p.Name)) -Force}
    foreach($name in $logs){if(Test-Path -LiteralPath (Join-Path $backup $name)){Copy-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $game $name) -Force}}
    throw
} finally {
    foreach($p in $plugins){$stage=Join-Path $game ('Bin\loader\'+$p.Name+'.clean-install-stage');if(Test-Path -LiteralPath $stage){Remove-Item -LiteralPath $stage}}
}
