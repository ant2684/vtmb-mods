[CmdletBinding()]
param([Parameter(Mandatory)][string]$Plugin,
      [Parameter(Mandatory)][string]$ServerDll,
      [string]$Python='python')

$ErrorActionPreference = 'Stop'
& $Python -B (Join-Path $PSScriptRoot 'tests\verify.py') $Plugin $ServerDll
if ($LASTEXITCODE -ne 0) { throw 'Exact clean-binary regression failed.' }
