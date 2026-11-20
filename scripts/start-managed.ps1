param([ValidateSet('MOCK','U8')][string]$Mode='MOCK',[int]$Port=8000,
      [string]$PgBin='C:\U8Runtime\pgsql\bin')
# Foreground supervisor. Its children are hidden. Ctrl+C stops owned children.
$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
$Backend=Join-Path $ProjectRoot 'backend'
$Python=Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$env:U8_MODE=$Mode
if (Test-Path -LiteralPath (Join-Path $PgBin 'pg_dump.exe')) {
    $env:PG_BIN=$PgBin
    $env:AUTO_BACKUP='1'
} else { Write-Warning 'PostgreSQL backup tools missing. Set -PgBin; backup alert remains active.' }
if ($Mode -eq 'U8' -and -not $env:U8_APP_KEY -and -not $env:U8_CREDENTIALS_HTML) { throw 'Set U8 credentials in environment first.' }
Set-Location $Backend
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; no processes started.' }
& $Python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',int('$Port'))); s.close()"
if ($LASTEXITCODE -ne 0) { throw "Port $Port is occupied. Stop the old service before starting managed mode." }
$commands=@(@('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$Port"),@('-m','app.tasks.worker'),@('-m','app.operations'))
$children=@{}
$failures=@{}
try {
    while ($true) {
        for ($i=0;$i -lt $commands.Count;$i++) {
            if (-not $children.ContainsKey($i) -or $children[$i].HasExited) {
                if ($children.ContainsKey($i)) {
                    $failures[$i]=1+[int]$failures[$i]
                    Write-Warning "Process $i exited; restart attempt $($failures[$i])"
                    if ($failures[$i] -ge 5) { throw "Process $i repeatedly failed. Inspect logs; automatic restarts stopped." }
                    Start-Sleep -Seconds ([Math]::Min(30,2*[int]$failures[$i]))
                }
                $children[$i]=Start-Process -FilePath $Python -ArgumentList $commands[$i] -WorkingDirectory $Backend -WindowStyle Hidden -PassThru
            }
        }
        Start-Sleep -Seconds 3
    }
} finally {
    foreach ($child in $children.Values) { if (-not $child.HasExited) { Stop-Process -Id $child.Id -ErrorAction SilentlyContinue } }
}
