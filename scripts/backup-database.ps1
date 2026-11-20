param([string]$PgBin)
$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
if ($PgBin) { $env:PG_BIN=$PgBin }
Set-Location (Join-Path $ProjectRoot 'backend')
& (Join-Path $ProjectRoot '.venv\Scripts\python.exe') -m app.backup
if ($LASTEXITCODE -ne 0) { throw 'Backup failed. Existing backups were preserved.' }
