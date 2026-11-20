param(
    [string]$CredentialsHtml='C:\U8Config\credentials.html',
    [int]$Port=8000
)
$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
$env:U8_MODE='U8'
$env:U8_ACCOUNT='999'
$env:U8_FROM_ACCOUNT='megsky'
$env:U8_TO_ACCOUNT='megsky'
$env:U8_CREDENTIALS_HTML=$CredentialsHtml
Set-Location (Join-Path $ProjectRoot 'backend')
$Python=Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Start PostgreSQL first; migration failed.' }
& (Join-Path $PSScriptRoot 'start-managed.ps1') -Mode U8 -Port $Port
