# Startup script for Hospital Management System (HMS)

$baseDir = "f:\Hospital Soft"
$binDir = "$baseDir\bin"
$env:PATH = "$binDir\nodejs;$binDir\python;$env:PATH"

# 1. Start Database
Write-Host "Starting PostgreSQL Database..." -ForegroundColor Cyan

# Stop any existing postgres instance cleanly
Stop-Process -Name "postgres" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Remove stale PID file
$postmasterLock = "$binDir\pgsql\data\postmaster.pid"
if (Test-Path $postmasterLock) {
    Remove-Item $postmasterLock -Force
    Write-Host "Removed stale PID file." -ForegroundColor Yellow
}

# Start postgres as a background process (keeps it alive as long as this script runs)
$pgProcess = Start-Process -FilePath "$binDir\pgsql\bin\postgres.exe" `
    -ArgumentList "-D `"$binDir\pgsql\data`"" `
    -WindowStyle Hidden -PassThru

# Wait for DB to accept connections
Write-Host "Waiting for Database to accept connections..." -ForegroundColor Yellow
$retries = 0
while ($retries -lt 30) {
    $result = & "$binDir\pgsql\bin\pg_isready.exe" -h 127.0.0.1 -p 5432 -q
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
    $retries++
}
Write-Host "Database is ready!" -ForegroundColor Green

# Create Windows user role if it doesn't exist (prevents crash on system auth)
$currentUser = $env:USERNAME
Write-Host "Ensuring DB role for '$currentUser' exists..." -ForegroundColor Yellow
& "$binDir\pgsql\bin\psql.exe" -U postgres -h 127.0.0.1 -c "DO `$`$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$currentUser') THEN EXECUTE format('CREATE ROLE %I SUPERUSER LOGIN', '$currentUser'); END IF; END `$`$;" 2>$null

# 2. Start Backend
Write-Host "Starting FastAPI Backend Server..." -ForegroundColor Cyan
Start-Process -FilePath "$binDir\python\python.exe" -ArgumentList "-m uvicorn backend.main:app --port 8000" -NoNewWindow -WorkingDirectory "$baseDir"

# 3. Start Frontend
Write-Host "Starting React Frontend Server..." -ForegroundColor Cyan
Start-Process -FilePath "$binDir\nodejs\npm.cmd" -ArgumentList "run dev -- --port 3000 --host" -NoNewWindow -WorkingDirectory "$baseDir\frontend"

Write-Host "`nApp successfully launched!" -ForegroundColor Green
Write-Host "➜ Backend API:  http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "➜ Frontend App: http://localhost:3000/" -ForegroundColor Blue
Write-Host "`nPress Enter to exit and stop all services..." -ForegroundColor Magenta

Read-Host

# Cleanup and Shutdown on Exit
Write-Host "`nStopping services..." -ForegroundColor Red
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue
& "$binDir\pgsql\bin\pg_ctl.exe" -D "$binDir\pgsql\data" stop
Write-Host "Services stopped. Goodbye!" -ForegroundColor Green
