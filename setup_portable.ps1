# Setup Portable Environment for Hospital Management System (HMS)
# Downloads and sets up portable Node.js, Python with pip, and PostgreSQL

$binDir = "d:\H\bin"
if (!(Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir | Out-Null
}

$tempDir = "d:\H\setup_temp"
if (!(Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir | Out-Null
}

# Helper to download and unzip
function Install-ZipPackage($url, $zipName, $destDirName) {
    $zipPath = "$tempDir\$zipName"
    $targetDir = "$binDir\$destDirName"
    
    if (!(Test-Path $targetDir)) {
        if (!(Test-Path $zipPath)) {
            Write-Host "Downloading $zipName..."
            Invoke-WebRequest -Uri $url -OutFile $zipPath
        }
        Write-Host "Extracting $zipName to $targetDir..."
        Expand-Archive -Path $zipPath -DestinationPath "$binDir" -Force
        # Rename extracted directory to target name if needed
        $extractedDir = Get-ChildItem "$binDir" | Where-Object { $_.PSIsContainer -and ($_.Name -like "*node*" -or $_.Name -like "*pgsql*") } | Select-Object -First 1
        if ($extractedDir -and $extractedDir.Name -ne $destDirName) {
            Rename-Item -Path $extractedDir.FullName -NewName $destDirName
        }
    } else {
        Write-Host "$destDirName already exists, skipping."
    }
}

# 1. Download and extract Node.js (Portable)
$nodeUrl = "https://nodejs.org/dist/v20.11.1/node-v20.11.1-win-x64.zip"
Install-ZipPackage -url $nodeUrl -zipName "node.zip" -destDirName "nodejs"

# 2. Download and extract Python (Embeddable)
$pythonTarget = "$binDir\python"
if (!(Test-Path $pythonTarget)) {
    New-Item -ItemType Directory -Path $pythonTarget | Out-Null
    $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
    $pyZip = "$tempDir\python.zip"
    if (!(Test-Path $pyZip)) {
        Write-Host "Downloading Python embeddable zip..."
        Invoke-WebRequest -Uri $pyUrl -OutFile $pyZip
    }
    Write-Host "Extracting Python..."
    Expand-Archive -Path $pyZip -DestinationPath $pythonTarget -Force
    
    # Enable site-packages in embeddable python (uncomment import site)
    $pthFile = "$pythonTarget\python311._pth"
    if (Test-Path $pthFile) {
        $content = Get-Content $pthFile
        $content = $content -replace '#import site', 'import site'
        Set-Content -Path $pthFile -Value $content
    }

    # Download and install pip
    Write-Host "Downloading get-pip.py..."
    $pipScript = "$tempDir\get-pip.py"
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $pipScript
    
    Write-Host "Installing pip..."
    Start-Process -FilePath "$pythonTarget\python.exe" -ArgumentList "`"$pipScript`"" -Wait
} else {
    Write-Host "Python already exists, skipping."
}

# 3. Download and extract PostgreSQL (Binaries)
$pgUrl = "https://get.enterprisedb.com/postgresql/postgresql-16.2-1-windows-x64-binaries.zip"
Install-ZipPackage -url $pgUrl -zipName "postgresql.zip" -destDirName "pgsql"

# Initialize PostgreSQL Database if data directory doesn't exist
$pgDataDir = "$binDir\pgsql\data"
if (!(Test-Path $pgDataDir)) {
    Write-Host "Initializing PostgreSQL Database..."
    $initDbPath = "$binDir\pgsql\bin\initdb.exe"
    Start-Process -FilePath $initDbPath -ArgumentList "-D `"$pgDataDir`" -U postgres -A trust" -Wait
} else {
    Write-Host "PostgreSQL Database already initialized."
}

# Create startup helper scripts in d:\H
Write-Host "Creating helper startup scripts..."

$startDbScript = @"
`$pgCtl = "d:\H\bin\pgsql\bin\pg_ctl.exe"
`$pgData = "d:\H\bin\pgsql\data"
& `$pgCtl -D `$pgData -l d:\H\pgsql.log start
Read-Host "PostgreSQL is running. Press Enter to stop it."
& `$pgCtl -D `$pgData stop
"@
Set-Content -Path "d:\H\start_db.ps1" -Value $startDbScript

Write-Host "Setup finished successfully!"
