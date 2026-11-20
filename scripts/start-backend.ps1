$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
$env:U8_MODE='MOCK'
$env:IMPORT_BATCH_SIZE='50'
Set-Location (Join-Path $ProjectRoot 'backend')
$Python=Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed. Start PostgreSQL first.' }
& (Join-Path $PSScriptRoot 'start-managed.ps1') -Mode MOCK -Port 8000
