# Setup Environment Script for Hospital Management System
# Downloads and installs Python, Node.js, and PostgreSQL

$setupDir = "d:\H\setup"
if (!(Test-Path $setupDir)) {
    New-Item -ItemType Directory -Path $setupDir | Out-Null
}

Write-Host "Starting downloads..."

# 1. Download Python 3.11.9
$pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
$pythonPath = "$setupDir\python-3.11.9.exe"
if (!(Test-Path $pythonPath)) {
    Write-Host "Downloading Python..."
    Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonPath
} else {
    Write-Host "Python installer already downloaded."
}

# 2. Download Node.js v20.11.1
$nodeUrl = "https://nodejs.org/dist/v20.11.1/node-v20.11.1-x64.msi"
$nodePath = "$setupDir\node-v20.11.1.msi"
if (!(Test-Path $nodePath)) {
    Write-Host "Downloading Node.js..."
    Invoke-WebRequest -Uri $nodeUrl -OutFile $nodePath
} else {
    Write-Host "Node.js installer already downloaded."
}

# 3. Download PostgreSQL 16.2
$pgUrl = "https://get.enterprisedb.com/postgresql/postgresql-16.2-1-windows-x64.exe"
$pgPath = "$setupDir\postgresql-16.2.exe"
if (!(Test-Path $pgPath)) {
    Write-Host "Downloading PostgreSQL..."
    try {
        Invoke-WebRequest -Uri $pgUrl -OutFile $pgPath
    } catch {
        Write-Warning "Direct PostgreSQL download failed, trying alternative zip..."
        $pgZipUrl = "https://get.enterprisedb.com/postgresql/postgresql-16.2-1-windows-x64-binaries.zip"
        $pgPath = "$setupDir\postgresql-16.2-binaries.zip"
        Invoke-WebRequest -Uri $pgZipUrl -OutFile $pgPath
    }
} else {
    Write-Host "PostgreSQL already downloaded."
}

Write-Host "Downloads complete. Starting silent installations..."

# Install Python
Write-Host "Installing Python (this will run in the background, please wait)..."
Start-Process -FilePath $pythonPath -ArgumentList "/passive PrependPath=1 Include_test=0" -Wait

# Install Node.js
Write-Host "Installing Node.js..."
Start-Process -FilePath msiexec.exe -ArgumentList "/i `"$nodePath`" /qn /norestart" -Wait

# Install PostgreSQL (if exe)
if ($pgPath.EndsWith(".exe")) {
    Write-Host "Installing PostgreSQL (Superuser password: 'postgres', Port: 5432)..."
    Start-Process -FilePath $pgPath -ArgumentList "--mode unattended --unattendedmodeui none --superuserpassword postgres --serverport 5432" -Wait
} else {
    Write-Host "Extracting PostgreSQL zip..."
    Expand-Archive -Path $pgPath -DestinationPath "$setupDir\pgsql" -Force
    Write-Host "Initializing PostgreSQL database..."
    Start-Process -FilePath "$setupDir\pgsql\pgsql\bin\initdb.exe" -ArgumentList "-D `"$setupDir\pgsql\data`" -U postgres" -Wait
}

Write-Host "Installation check complete."
