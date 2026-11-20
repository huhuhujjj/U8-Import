param([string]$Runtime='C:\U8Runtime')
$ErrorActionPreference='Stop'
$PgBin=Join-Path $Runtime 'pgsql\bin'
$PgData=Join-Path $Runtime 'pgdata'
& (Join-Path $PgBin 'pg_isready.exe') -h 127.0.0.1 -p 55432 -q
if ($LASTEXITCODE -eq 0) { Write-Output 'PostgreSQL is already running on localhost:55432'; exit 0 }
if (-not (Test-Path -LiteralPath (Join-Path $PgData 'PG_VERSION'))) { throw 'Initialized PostgreSQL data directory is missing.' }
& (Join-Path $PgBin 'postgres.exe') -D $PgData
