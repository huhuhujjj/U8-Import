param([ValidateSet('MOCK','U8')][string]$Mode='MOCK')
$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
$env:U8_MODE=$Mode
Set-Location (Join-Path $ProjectRoot 'backend')
& (Join-Path $ProjectRoot '.venv\Scripts\python.exe') -m app.tasks.worker
exit $LASTEXITCODE
