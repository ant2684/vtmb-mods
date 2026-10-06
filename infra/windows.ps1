[CmdletBinding()]
param([ValidateSet('Inspect','Launch','Stop','RestoreSettings')][string]$Action,
      [string]$GameRoot, [string]$LaunchUser, [string]$InputFile, [string]$OutputFile,
      [string]$FixtureRegistry='')
$ErrorActionPreference='Stop'
if((whoami.exe).Trim() -ne $LaunchUser){throw 'Real Windows launch user required; sandbox HKCU is not evidence'}
$registryBase='Software\Troika\Vampire'
if($FixtureRegistry){
    if($FixtureRegistry -notmatch '^Software\\VTMBRegressionFixture_[0-9a-f]{32}$' -or $Action -notin @('Inspect','RestoreSettings')){throw 'Only isolated owned registry fixtures are supported'}
    $registryBase=$FixtureRegistry
}
function Video {
    foreach($sub in @('Settings','ResPatch')) {
        $path='HKCU:\'+$registryBase+'\'+$sub
        if(-not(Test-Path -LiteralPath $path)){[pscustomobject]@{Sub=$sub;Exists=$false;Values=@()};continue}
        $key=Get-Item -LiteralPath $path
        [pscustomobject]@{Sub=$sub;Exists=$true;Values=@(foreach($name in $key.GetValueNames()|Sort-Object){[pscustomobject]@{Name=$name;Kind=$key.GetValueKind($name).ToString();Value=$key.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)}})}
    }
}
function Links {
    if($FixtureRegistry){return}
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
    foreach($candidate in $launchData.Candidates){if((Get-FileHash -LiteralPath $candidate.Path).Hash -ne $candidate.Hash){throw 'Temporary installed candidate changed before launch'}}
    foreach($arg in $launchData.Arguments) {if($arg -in @('-condebug','-window','-windowed','-sw','-fullscreen','-full','-w','-width','-h','-height')){throw 'Forbidden video/debug argument'}}
    $process=Start-Process -FilePath (Join-Path $GameRoot 'Vampire.exe') -WorkingDirectory $GameRoot -ArgumentList @($launchData.Arguments) -WindowStyle Hidden -PassThru
    @{Id=$process.Id;Ticks=$process.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath $OutputFile
} elseif($Action -eq 'Stop') {
    $owned=Get-Content -LiteralPath $InputFile -Raw | ConvertFrom-Json
    $process=Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
    if($process){if($process.ProcessName -ne 'vampire' -or $process.StartTime.ToUniversalTime().Ticks -ne $owned.Ticks){throw 'PID/start-time ownership differs'};Stop-Process -Id $process.Id;$process.WaitForExit(10000)|Out-Null}
} elseif($Action -eq 'RestoreSettings') {
    if(-not $FixtureRegistry -and (Get-Process Vampire -ErrorAction SilentlyContinue)){throw 'Refuse settings restoration while game runs'}
    $snapshot=Get-Content -LiteralPath $InputFile -Raw|ConvertFrom-Json
    if($snapshot.User -ne $LaunchUser){throw 'Settings snapshot belongs to another Windows user'}
    function Intent($operation,$target,$value) {
        $record=@{Operation=$operation;Target=$target;Value=$value;UTC=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 10 -Compress
        $bytes=[Text.Encoding]::UTF8.GetBytes($record+[Environment]::NewLine)
        $stream=[IO.File]::Open((Join-Path (Split-Path $InputFile) 'settings-intents.jsonl'),[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::Read)
        try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
    }
    foreach($sub in $snapshot.Video) {
        if($sub.Sub -notin @('Settings','ResPatch')){throw 'Unknown video snapshot key'}
        $path='HKCU:\'+$registryBase+'\'+$sub.Sub
        if(-not $sub.Exists){if(Test-Path -LiteralPath $path){Intent 'DeleteNewKey' $path $null;Remove-Item -LiteralPath $path};continue}
        if(-not(Test-Path -LiteralPath $path)){Intent 'CreateOriginalKey' $path $null;New-Item -Path $path -Force|Out-Null}
        $key=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey(($registryBase+'\'+$sub.Sub),$true)
        if(-not $key){throw 'Writable original registry key unavailable'}
        try {
            foreach($name in $key.GetValueNames()){if(-not($sub.Values|Where-Object Name -EQ $name)){Intent 'DeleteNewValue' ($path+'\'+$name) $null;$key.DeleteValue($name)}}
            foreach($value in $sub.Values){
                $kind=[Enum]::Parse([Microsoft.Win32.RegistryValueKind],$value.Kind)
                $typed=switch($value.Kind){'DWord'{[int]$value.Value};'QWord'{[long]$value.Value};'Binary'{,[byte[]]$value.Value};'MultiString'{,[string[]]$value.Value};'None'{,[byte[]]$value.Value};default{[string]$value.Value}}
                $exists=$value.Name -in $key.GetValueNames()
                $actual=$key.GetValue($value.Name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                $equal=$exists -and $key.GetValueKind($value.Name) -eq $kind -and (ConvertTo-Json -InputObject $actual -Compress) -eq (ConvertTo-Json -InputObject $typed -Compress)
                if(-not $equal){Intent 'RestoreOriginalValue' ($path+'\'+$value.Name) $value;$key.SetValue($value.Name,$typed,$kind)}
            }
        } finally{$key.Dispose()}
    }
    foreach($original in $snapshot.Shortcuts) {
        $shell=New-Object -ComObject WScript.Shell;$link=$shell.CreateShortcut($original.Path)
        if($link.TargetPath -ne $original.Target -or $link.Arguments -ne $original.Arguments -or $link.WorkingDirectory -ne $original.WorkingDirectory){Intent 'RestoreShortcut' $original.Path $original;$link.TargetPath=$original.Target;$link.Arguments=$original.Arguments;$link.WorkingDirectory=$original.WorkingDirectory;$link.Save()}
    }
}
