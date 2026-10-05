[CmdletBinding()]
param([ValidateSet('Inspect','Launch','Stop','RestoreSettings')][string]$Action,
      [string]$GameRoot, [string]$LaunchUser, [string]$InputFile, [string]$OutputFile)
$ErrorActionPreference='Stop'
if((whoami.exe).Trim() -ne $LaunchUser){throw 'Real Windows launch user required; sandbox HKCU is not evidence'}
function Video {
    foreach($sub in @('Settings','ResPatch')) {
        $path='HKCU:\Software\Troika\Vampire\'+$sub
        if(-not(Test-Path -LiteralPath $path)){[pscustomobject]@{Sub=$sub;Exists=$false;Values=@()};continue}
        $key=Get-Item -LiteralPath $path
        [pscustomobject]@{Sub=$sub;Exists=$true;Values=@(foreach($name in $key.GetValueNames()|Sort-Object){[pscustomobject]@{Name=$name;Kind=$key.GetValueKind($name).ToString();Value=$key.GetValue($name)}})}
    }
}
function Links {
    $shell=New-Object -ComObject WScript.Shell
    foreach($dir in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'))) {
        foreach($file in Get-ChildItem -LiteralPath $dir -Filter '*.lnk' -File) {
            $link=$shell.CreateShortcut($file.FullName)
            if($link.TargetPath -match 'Vampire|Bloodlines|Loader'){[pscustomobject]@{Path=$file.FullName;Target=$link.TargetPath;Arguments=$link.Arguments;WorkingDirectory=$link.WorkingDirectory}}
        }
    }
}
if($Action -eq 'Inspect') {
    @{User=(whoami.exe).Trim();Video=@(Video);Shortcuts=@(Links);Processes=@(Get-Process Vampire -ErrorAction SilentlyContinue | ForEach-Object {@{Id=$_.Id;Ticks=$_.StartTime.ToUniversalTime().Ticks}})} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputFile
} elseif($Action -eq 'Launch') {
    if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'User game is already running'}
    $launchData=Get-Content -LiteralPath $InputFile -Raw | ConvertFrom-Json
    foreach($arg in $launchData.Arguments) {if($arg -in @('-condebug','-window','-windowed','-sw','-fullscreen','-full','-w','-width','-h','-height')){throw 'Forbidden video/debug argument'}}
    $process=Start-Process -FilePath (Join-Path $GameRoot 'Vampire.exe') -WorkingDirectory $GameRoot -ArgumentList @($launchData.Arguments) -WindowStyle Hidden -PassThru
    @{Id=$process.Id;Ticks=$process.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath $OutputFile
} elseif($Action -eq 'Stop') {
    $owned=Get-Content -LiteralPath $InputFile -Raw | ConvertFrom-Json
    $process=Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
    if($process){if($process.ProcessName -ne 'vampire' -or $process.StartTime.ToUniversalTime().Ticks -ne $owned.Ticks){throw 'PID/start-time ownership differs'};Stop-Process -Id $process.Id;$process.WaitForExit(10000)|Out-Null}
} elseif($Action -eq 'RestoreSettings') {
    if(Get-Process Vampire -ErrorAction SilentlyContinue){throw 'Refuse settings restoration while game runs'}
    $snapshot=Get-Content -LiteralPath $InputFile -Raw|ConvertFrom-Json
    foreach($sub in $snapshot.Video) {
        $path='HKCU:\Software\Troika\Vampire\'+$sub.Sub
        if(-not $sub.Exists){if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path};continue}
        if(-not(Test-Path -LiteralPath $path)){New-Item -Path $path -Force|Out-Null}
        $key=Get-Item -LiteralPath $path
        foreach($name in $key.GetValueNames()){if(-not($sub.Values|Where-Object Name -EQ $name)){$key.DeleteValue($name)}}
        foreach($value in $sub.Values){$key.SetValue($value.Name,$value.Value,[Microsoft.Win32.RegistryValueKind]::$($value.Kind))}
    }
    foreach($original in $snapshot.Shortcuts) {
        $shell=New-Object -ComObject WScript.Shell;$link=$shell.CreateShortcut($original.Path)
        if($link.TargetPath -ne $original.Target -or $link.Arguments -ne $original.Arguments -or $link.WorkingDirectory -ne $original.WorkingDirectory){$link.TargetPath=$original.Target;$link.Arguments=$original.Arguments;$link.WorkingDirectory=$original.WorkingDirectory;$link.Save()}
    }
}
