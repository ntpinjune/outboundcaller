# Start Web Server + ngrok Tunnel for Remote Access
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Remote Access Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set password (optional but recommended)
if (-not $env:WEB_SERVER_PASSWORD) {
    Write-Host "[!] No password set. It's recommended to set one for security!" -ForegroundColor Yellow
    Write-Host ""
    $setPassword = Read-Host "Set a password? (y/n)"
    if ($setPassword -eq "y" -or $setPassword -eq "Y") {
        $password = Read-Host "Enter password" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
        $plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
        $env:WEB_SERVER_PASSWORD = $plainPassword
        Write-Host "[OK] Password set!" -ForegroundColor Green
        Write-Host ""
    }
}

# Check if web server is already running
$webServerRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    $webServerRunning = $true
} catch {
    $webServerRunning = $false
}

if ($webServerRunning) {
    Write-Host "[OK] Web server is already running on port 5000" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "Starting web server..." -ForegroundColor Yellow
    
    # Start web server in background
    $webServerJob = Start-Job -ScriptBlock {
        Set-Location $using:PWD
        $env:WEB_SERVER_PASSWORD = $using:env:WEB_SERVER_PASSWORD
        .\venv\Scripts\python.exe web_server.py
    }
    
    Write-Host "[OK] Web server starting in background (job ID: $($webServerJob.Id))" -ForegroundColor Green
    
    # Wait for server to start (Flask debug mode restarts once, so wait longer)
    Write-Host "Waiting for web server to start..." -ForegroundColor Gray
    $maxRetries = 10
    $retryCount = 0
    $serverReady = $false
    
    while ($retryCount -lt $maxRetries -and -not $serverReady) {
        Start-Sleep -Seconds 2
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:5000/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            $serverReady = $true
            Write-Host "[OK] Web server is running!" -ForegroundColor Green
            Write-Host ""
        } catch {
            $retryCount++
            if ($retryCount -ge $maxRetries) {
                Write-Host "[ERROR] Web server failed to start after $($maxRetries * 2) seconds" -ForegroundColor Red
                Write-Host "Checking job output..." -ForegroundColor Yellow
                $jobOutput = Receive-Job -Job $webServerJob
                Write-Host $jobOutput -ForegroundColor Gray
                Stop-Job -Job $webServerJob
                Remove-Job -Job $webServerJob
                exit 1
            }
            # Continue waiting
        }
    }
}

# Find ngrok
$ngrokPath = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrokPath) {
    # Check if ngrok.exe exists in current directory
    if (Test-Path "$PWD\ngrok.exe") {
        $ngrokCmd = "$PWD\ngrok.exe"
        Write-Host "[OK] Found ngrok.exe in current directory" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] ngrok is not installed or not found in PATH" -ForegroundColor Red
        Write-Host ""
        Write-Host "To install ngrok:" -ForegroundColor Yellow
        Write-Host "1. Run: .\setup_ngrok.ps1" -ForegroundColor Cyan
        Write-Host "2. Or download from: https://ngrok.com/download" -ForegroundColor Cyan
        Write-Host ""
        exit 1
    }
} else {
    $ngrokCmd = "ngrok"
    Write-Host "[OK] Found ngrok: $($ngrokPath.Source)" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting ngrok tunnel..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[!] Keep this window open while using ngrok!" -ForegroundColor Yellow
Write-Host "   The tunnel will close if you close this window." -ForegroundColor Gray
Write-Host ""
Write-Host "[INFO] The ngrok URL will appear below." -ForegroundColor Cyan
Write-Host "   Share this URL with your friend!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop both ngrok and the web server" -ForegroundColor Gray
Write-Host ""

# Start ngrok (this will run in foreground)
try {
    & $ngrokCmd http 5000
} finally {
    # Cleanup: Stop web server job if we started it
    if ($webServerJob) {
        Write-Host ""
        Write-Host "Stopping web server..." -ForegroundColor Yellow
        Stop-Job -Job $webServerJob
        Remove-Job -Job $webServerJob
        Write-Host "[OK] Web server stopped" -ForegroundColor Green
    }
}
