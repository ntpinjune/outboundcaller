# Setup script for ngrok tunnel
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ngrok Setup for Remote Access" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if ngrok is already installed
$ngrokPath = Get-Command ngrok -ErrorAction SilentlyContinue

if (-not $ngrokPath) {
    Write-Host "ngrok is not installed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To install ngrok:" -ForegroundColor White
    Write-Host "1. Go to: https://ngrok.com/download" -ForegroundColor Cyan
    Write-Host "2. Download the Windows version" -ForegroundColor Cyan
    Write-Host "3. Extract ngrok.exe to a folder in your PATH (e.g., C:\Windows\System32 or C:\tools)" -ForegroundColor Cyan
    Write-Host "4. Or extract to this directory: $PWD" -ForegroundColor Cyan
    Write-Host ""
    
    # Check if ngrok.exe exists in current directory
    if (Test-Path "$PWD\ngrok.exe") {
        Write-Host "✅ Found ngrok.exe in current directory!" -ForegroundColor Green
        $useLocal = $true
    } else {
        Write-Host "Would you like to download ngrok now? (This will download to current directory)" -ForegroundColor Yellow
        $download = Read-Host "Download ngrok? (y/n)"
        
        if ($download -eq "y" -or $download -eq "Y") {
            Write-Host ""
            Write-Host "Downloading ngrok..." -ForegroundColor Yellow
            
            # Download ngrok for Windows
            $downloadUrl = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
            $zipPath = "$PWD\ngrok.zip"
            $extractPath = $PWD
            
            try {
                Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
                Write-Host "✅ Downloaded ngrok.zip" -ForegroundColor Green
                
                # Extract
                Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
                Write-Host "✅ Extracted ngrok.exe" -ForegroundColor Green
                
                # Clean up zip
                Remove-Item $zipPath -Force
                Write-Host "✅ Cleaned up" -ForegroundColor Green
                
                $useLocal = $true
            } catch {
                Write-Host "❌ Failed to download: $_" -ForegroundColor Red
                Write-Host ""
                Write-Host "Please download manually from: https://ngrok.com/download" -ForegroundColor Yellow
                exit 1
            }
        } else {
            Write-Host ""
            Write-Host "Please install ngrok manually, then run this script again." -ForegroundColor Yellow
            exit 1
        }
    }
} else {
    Write-Host "✅ ngrok is already installed!" -ForegroundColor Green
    Write-Host "   Location: $($ngrokPath.Source)" -ForegroundColor Gray
    $useLocal = $false
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if ngrok auth token is set
$ngrokToken = $env:NGROK_AUTHTOKEN
if (-not $ngrokToken) {
    Write-Host "⚠️  ngrok auth token not set" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To get your free ngrok auth token:" -ForegroundColor White
    Write-Host "1. Sign up at: https://dashboard.ngrok.com/signup" -ForegroundColor Cyan
    Write-Host "2. Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken" -ForegroundColor Cyan
    Write-Host "3. Set it as environment variable:" -ForegroundColor Cyan
    Write-Host '   $env:NGROK_AUTHTOKEN = "your-token-here"' -ForegroundColor Gray
    Write-Host ""
    Write-Host "Or run: .\ngrok.exe config add-authtoken YOUR_TOKEN" -ForegroundColor Cyan
    Write-Host ""
    
    $token = Read-Host "Enter your ngrok auth token (or press Enter to skip)"
    if ($token) {
        # Set auth token
        if ($useLocal) {
            & "$PWD\ngrok.exe" config add-authtoken $token
        } else {
            ngrok config add-authtoken $token
        }
        Write-Host "✅ Auth token configured!" -ForegroundColor Green
    }
} else {
    Write-Host "✅ ngrok auth token is configured" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting ngrok tunnel" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if web server is running
$webServerRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    $webServerRunning = $true
} catch {
    $webServerRunning = $false
}

if (-not $webServerRunning) {
    Write-Host "⚠️  Web server is not running on port 5000" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please start the web server first:" -ForegroundColor White
    Write-Host "  .\venv\Scripts\python.exe web_server.py" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Then run this script again, or start ngrok manually:" -ForegroundColor White
    if ($useLocal) {
        Write-Host "  .\ngrok.exe http 5000" -ForegroundColor Cyan
    } else {
        Write-Host "  ngrok http 5000" -ForegroundColor Cyan
    }
    exit 1
} else {
    Write-Host "✅ Web server is running on port 5000" -ForegroundColor Green
    Write-Host ""
    
    # Start ngrok
    Write-Host "Starting ngrok tunnel..." -ForegroundColor Yellow
    Write-Host "This will create a public URL that your friend can access." -ForegroundColor Gray
    Write-Host ""
    Write-Host "⚠️  Keep this window open while using ngrok!" -ForegroundColor Yellow
    Write-Host "   The tunnel will close if you close this window." -ForegroundColor Gray
    Write-Host ""
    
    if ($useLocal) {
        & "$PWD\ngrok.exe" http 5000
    } else {
        ngrok http 5000
    }
}
