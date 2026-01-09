# Direct installer execution script
$installerPath = "$env:TEMP\python-3.13.1-installer.exe"

if (Test-Path $installerPath) {
    Write-Host "Running Python installer..." -ForegroundColor Cyan
    Write-Host "Location: $installerPath" -ForegroundColor Gray
    Write-Host ""
    Write-Host "IMPORTANT: Check 'Add Python to PATH' during installation!" -ForegroundColor Yellow
    Write-Host ""
    
    # Run the installer directly
    Start-Process -FilePath $installerPath -Wait
    
    Write-Host ""
    Write-Host "Installation complete! Now run: .\recreate_venv.ps1" -ForegroundColor Green
} else {
    Write-Host "Installer not found at: $installerPath" -ForegroundColor Red
    Write-Host "Run: .\download_python.ps1 first" -ForegroundColor Yellow
}
