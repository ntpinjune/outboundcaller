# Script to recreate virtual environment with Python 3.13.1 or 3.12
# Run this after installing Python

Write-Host "Recreating virtual environment..." -ForegroundColor Cyan

# Deactivate current venv if active
if ($env:VIRTUAL_ENV) {
    Write-Host "Deactivating current virtual environment..." -ForegroundColor Yellow
    deactivate
}

# Check for running Python processes that might lock files
Write-Host "Checking for running Python processes..." -ForegroundColor Cyan
$pythonProcesses = Get-Process python* -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*outboundcaller-1*" }
if ($pythonProcesses) {
    Write-Host "Found running Python processes. Stopping them..." -ForegroundColor Yellow
    $pythonProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Remove old venv (with retry for locked files)
if (Test-Path "venv") {
    Write-Host "Removing old virtual environment..." -ForegroundColor Yellow
    try {
        Remove-Item -Recurse -Force venv -ErrorAction Stop
    } catch {
        Write-Host "Some files are locked. Retrying after a moment..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
        # Try to unlock DLL files specifically
        Get-ChildItem -Path venv -Recurse -Filter "*.dll" -ErrorAction SilentlyContinue | ForEach-Object {
            try { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue } catch {}
        }
        Remove-Item -Recurse -Force venv -ErrorAction SilentlyContinue
    }
}

# Check for Python versions (prefer 3.13.1, fallback to 3.12)
$pythonVersion = $null
$pythonCmd = $null

Write-Host "Checking for Python versions..." -ForegroundColor Cyan

# Try Python 3.13.1 first
try {
    $py313 = & py -3.13 --version 2>$null
    if ($py313) {
        $pythonVersion = "3.13"
        $pythonExe = "py"
        $pythonArgs = @("-3.13", "-m", "venv", "venv")
        Write-Host "Found: $py313" -ForegroundColor Green
    }
} catch {}

# Fallback to Python 3.12
if (-not $pythonVersion) {
    try {
        $py312 = & py -3.12 --version 2>$null
        if ($py312) {
            $pythonVersion = "3.12"
            $pythonExe = "py"
            $pythonArgs = @("-3.12", "-m", "venv", "venv")
            Write-Host "Found: $py312" -ForegroundColor Green
        }
    } catch {}
}

if ($pythonVersion) {
    # Create new venv
    Write-Host "Creating new virtual environment with Python $pythonVersion..." -ForegroundColor Cyan
    & $pythonExe $pythonArgs
    
    # Activate and upgrade pip
    Write-Host "Activating virtual environment and upgrading pip..." -ForegroundColor Cyan
    .\venv\Scripts\activate
    python -m pip install --upgrade pip
    
    # Install dependencies
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    pip install -r requirements.txt
    
    # Download additional files
    Write-Host "Downloading additional files..." -ForegroundColor Cyan
    python agent.py download-files
    
    Write-Host "`n✅ Virtual environment recreated successfully!" -ForegroundColor Green
    Write-Host "You can now run:" -ForegroundColor Yellow
    Write-Host "  .\venv\Scripts\activate" -ForegroundColor White
    Write-Host "  python agent.py dev" -ForegroundColor White
    
} else {
    Write-Host "`n❌ Python 3.13 or 3.12 not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.13.1 or 3.12 from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Or run: .\download_python.ps1" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    exit 1
}
