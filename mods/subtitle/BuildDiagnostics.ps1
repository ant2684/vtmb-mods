[CmdletBinding()]
param([string]$Zig='zig')
$ErrorActionPreference='Stop'
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path $PSScriptRoot 'build\zig-cache'
$tests=Join-Path $PSScriptRoot 'tests'
& $Zig c++ -target x86_64-windows-gnu -municode -O2 -o (Join-Path $tests 'capture_audio.exe') (Join-Path $tests 'capture_audio.cpp') -lole32 -lmmdevapi -luuid
if($LASTEXITCODE -ne 0){throw 'Process audio capture compilation failed'}
& $Zig c++ -target x86_64-windows-gnu -municode -O2 -o (Join-Path $tests 'mf_decode.exe') (Join-Path $tests 'mf_decode.cpp') -lole32 -lmfplat -lmfreadwrite -lmfuuid
if($LASTEXITCODE -ne 0){throw 'Source audio decoder compilation failed'}
