# Script to download and install Python 3.13.1
# Note: Python 3.12 is recommended for better compatibility

Write-Host "Python Download Script" -ForegroundColor Cyan
Write-Host "=====================" -ForegroundColor Cyan
Write-Host ""

$pythonVersion = "3.13.1"
$downloadUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-amd64.exe"
$installerPath = "$env:TEMP\python-$pythonVersion-installer.exe"

Write-Host "Downloading Python $pythonVersion..." -ForegroundColor Yellow
Write-Host "URL: $downloadUrl" -ForegroundColor Gray

try {
    # Download Python installer
    Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing
    
    Write-Host "`n✅ Download complete!" -ForegroundColor Green
    Write-Host "Installer saved to: $installerPath" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Run the installer: $installerPath" -ForegroundColor White
    Write-Host "2. IMPORTANT: Check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    Write-Host "3. After installation, run: .\recreate_venv.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "Would you like to open the installer now? (Y/N)" -ForegroundColor Cyan
    $response = Read-Host
    
    if ($response -eq 'Y' -or $response -eq 'y') {
        Write-Host "Opening installer..." -ForegroundColor Yellow
        Start-Process $installerPath
    } else {
        Write-Host "You can run the installer later from: $installerPath" -ForegroundColor Gray
    }
    
} catch {
    Write-Host "`n❌ Download failed!" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Alternative: Download manually from:" -ForegroundColor Yellow
    Write-Host "https://www.python.org/downloads/release/python-3131/" -ForegroundColor White
    exit 1
}
