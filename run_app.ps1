# =============================================================================
#  Hospital OS - local deployment (single service)
#
#  Serves the API and the bundled React UI from one process on one port:
#      http://127.0.0.1:8000
#
#  Usage:
#      .\run_app.ps1                  # build the UI if needed, then serve
#      .\run_app.ps1 -Rebuild         # force a fresh frontend build
#      .\run_app.ps1 -Port 8080       # different port
#      .\run_app.ps1 -NoBuild         # never run npm (UI must already be built)
#
#  Stop with Ctrl+C. Only the process this script started is stopped; unlike the
#  previous version it does NOT blanket-kill every python/node process on the box.
# =============================================================================
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$Rebuild,
    [switch]$NoBuild,
    [switch]$Seed
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# --- 1. Python ---------------------------------------------------------------
Write-Step 'Checking Python'
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw 'Python was not found on PATH. Install Python 3.11+ and retry.' }
Write-Ok "$python ($(python --version 2>&1))"

Write-Step 'Checking Python dependencies'
$missing = python -c @"
import importlib.util as u, sys
need = {'fastapi':'fastapi','uvicorn':'uvicorn','sqlalchemy':'SQLAlchemy','jose':'python-jose','bcrypt':'bcrypt','multipart':'python-multipart'}
missing = [pkg for mod, pkg in need.items() if u.find_spec(mod) is None]
print(' '.join(missing))
"@
if ($missing) {
    Write-Warn "Missing: $missing"
    Write-Step 'Installing from requirements.txt'
    python -m pip install -r requirements.txt
} else {
    Write-Ok 'all present'
}

# --- 2. Frontend build -------------------------------------------------------
$dist = Join-Path $root 'frontend\dist\index.html'
$needsBuild = $Rebuild -or (-not (Test-Path $dist))

if ($NoBuild) {
    if (-not (Test-Path $dist)) { throw "frontend\dist is missing and -NoBuild was given." }
    Write-Ok 'Using the existing frontend build'
}
elseif ($needsBuild) {
    Write-Step 'Building the frontend'
    if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
        Write-Warn 'node_modules missing - running npm install first'
        Push-Location (Join-Path $root 'frontend')
        try { npm install } finally { Pop-Location }
    }
    Push-Location (Join-Path $root 'frontend')
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'npm run build failed.' }
    } finally { Pop-Location }
    Write-Ok 'frontend built'
} else {
    Write-Ok 'Using the existing frontend build (use -Rebuild to refresh it)'
}

# --- 3. Environment ----------------------------------------------------------
if (-not $env:SECRET_KEY) {
    # Generated once and reused via .secret_key so logins survive a restart.
    Write-Warn 'SECRET_KEY not set - backend will generate and persist one in .secret_key'
}
$env:SERVE_FRONTEND = 'true'

Write-Step 'Database'
if ($env:DATABASE_URL) {
    Write-Ok "DATABASE_URL from environment: $env:DATABASE_URL"
} else {
    # Let backend/database.py resolve the SQLite file relative to the project root
    # (it handles the spaces in this checkout's path, a hand-built URL would not).
    Write-Ok "default: $root\hms_local.db"
    Write-Warn 'Set DATABASE_URL to use PostgreSQL, e.g. postgresql+psycopg2://user:pass@host/hms'
}

# --- 4. Port check -----------------------------------------------------------
# Get-NetTCPConnection is not dependable on every host, so probe the port directly.
$free = $false
try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $listener.Start()
    $listener.Stop()
    $free = $true
} catch {
    $free = $false
}
if (-not $free) {
    throw "Port $Port is already in use. Stop that process or run:  .\run_app.ps1 -Port 8080"
}

# --- 5. Serve ----------------------------------------------------------------
Write-Step "Starting Hospital OS on http://127.0.0.1:$Port"
Write-Host ''
Write-Host "    App      : http://127.0.0.1:$Port/"      -ForegroundColor White
Write-Host "    API docs : http://127.0.0.1:$Port/docs"  -ForegroundColor Gray
Write-Host "    Health   : http://127.0.0.1:$Port/health" -ForegroundColor Gray
Write-Host ''

if ($Seed) {
    Write-Warn 'Seed after login: POST /seed/ with an admin token, or use Admin Settings.'
}

Write-Host 'Press Ctrl+C to stop the server.' -ForegroundColor Green
Write-Host ''

# Run uvicorn in the foreground so this process *is* the server: Ctrl+C stops it,
# and no child process is left orphaned (spawning + Wait-Process is unreliable
# under restricted process permissions).
& $python -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
