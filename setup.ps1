# Outbound Caller Agent - Setup Script for Windows PowerShell
# This script automates the setup process for a new computer

$ErrorActionPreference = "Stop"

Write-Host "🚀 Outbound Caller Agent - Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Function to print colored messages
function Print-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Print-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Print-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Print-Info {
    param([string]$Message)
    Write-Host "ℹ️  $Message" -ForegroundColor Cyan
}

# Check if Git is installed
Write-Host "Checking prerequisites..." -ForegroundColor Cyan
try {
    $gitVersion = git --version 2>&1
    Print-Success "Git is installed: $gitVersion"
} catch {
    Print-Error "Git is not installed. Please install Git first:"
    Write-Host "  Download from: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# Check Python version
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+)\.(\d+)") {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]
        
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
            Print-Error "Python 3.11 or higher is required. Found: $pythonVersion"
            exit 1
        }
        Print-Success "Python is installed: $pythonVersion"
    } else {
        Print-Error "Could not determine Python version"
        exit 1
    }
} catch {
    Print-Error "Python 3 is not installed. Please install Python 3.11 or higher."
    Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Check if pip is installed
try {
    $pipVersion = pip --version 2>&1
    Print-Success "pip is installed"
} catch {
    Print-Error "pip is not installed. Please install pip first."
    exit 1
}

Write-Host ""
Write-Host "Setting up virtual environment..." -ForegroundColor Cyan

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Print-Info "Creating virtual environment..."
    python -m venv venv
    Print-Success "Virtual environment created"
} else {
    Print-Warning "Virtual environment already exists. Skipping creation."
}

# Activate virtual environment
Print-Info "Activating virtual environment..."
& "venv\Scripts\Activate.ps1"

# Upgrade pip
Print-Info "Upgrading pip..."
python -m pip install --upgrade pip --quiet

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Cyan
if (Test-Path "requirements.txt") {
    Print-Info "Installing packages from requirements.txt..."
    pip install -r requirements.txt
    Print-Success "Dependencies installed"
} else {
    Print-Error "requirements.txt not found!"
    exit 1
}

# Download model files
Write-Host ""
Write-Host "Downloading model files..." -ForegroundColor Cyan
try {
    python agent.py download-files 2>&1 | Out-Null
    Print-Success "Model files downloaded"
} catch {
    Print-Warning "Model download command not available or failed (this is okay)"
}

# Check for LiveKit CLI
Write-Host ""
try {
    $lkVersion = lk --version 2>&1
    Print-Success "LiveKit CLI is installed"
} catch {
    Print-Warning "LiveKit CLI is not installed. Installing now..."
    try {
        Invoke-WebRequest -Uri "https://get.livekit.io/cli.ps1" -UseBasicParsing | Invoke-Expression
        Print-Success "LiveKit CLI installed"
    } catch {
        Print-Warning "Failed to install LiveKit CLI automatically. Please install manually:"
        Write-Host "  iwr https://get.livekit.io/cli.ps1 -useb | iex" -ForegroundColor Yellow
    }
}

# Check for .env.local
Write-Host ""
if (Test-Path ".env.local") {
    Print-Success ".env.local file exists"
} else {
    Print-Warning ".env.local file not found!"
    Write-Host ""
    Write-Host "You need to create .env.local with the following required variables:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  LIVEKIT_URL=https://your-livekit-url.livekit.cloud"
    Write-Host "  LIVEKIT_API_KEY=your_api_key"
    Write-Host "  LIVEKIT_API_SECRET=your_api_secret"
    Write-Host "  SIP_OUTBOUND_TRUNK_ID=your_trunk_id"
    Write-Host "  OPENAI_API_KEY=your_openai_key (or GROQ_API_KEY)"
    Write-Host "  ELEVEN_API_KEY=your_elevenlabs_key"
    Write-Host "  GOOGLE_SHEET_ID=your_spreadsheet_id"
    Write-Host "  LANGFUSE_PUBLIC_KEY=your_public_key"
    Write-Host "  LANGFUSE_SECRET_KEY=your_secret_key"
    Write-Host ""
    Write-Host "See SETUP.md for the complete list of environment variables." -ForegroundColor Yellow
    Write-Host ""
    $response = Read-Host "Would you like to create .env.local now? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        New-Item -ItemType File -Path ".env.local" | Out-Null
        Print-Success ".env.local file created. Please edit it with your API keys."
    }
}

# Check for Google OAuth credentials
Write-Host ""
$oauthFiles = Get-ChildItem -Path "." -Filter "client_secret_*.json" -ErrorAction SilentlyContinue
if ($oauthFiles) {
    Print-Success "Google OAuth credentials found"
} else {
    Print-Warning "Google OAuth credentials (client_secret_*.json) not found!"
    Write-Host "  You'll need to:" -ForegroundColor Yellow
    Write-Host "  1. Go to https://console.cloud.google.com/" -ForegroundColor Yellow
    Write-Host "  2. Enable Google Calendar API and Google Sheets API" -ForegroundColor Yellow
    Write-Host "  3. Create OAuth 2.0 credentials" -ForegroundColor Yellow
    Write-Host "  4. Download as JSON and place in project root" -ForegroundColor Yellow
}

# Verify installation
Write-Host ""
Write-Host "Verifying installation..." -ForegroundColor Cyan
Write-Host ""

# Test imports
try {
    python -c "import livekit.agents" 2>&1 | Out-Null
    Print-Success "LiveKit agents module imported successfully"
} catch {
    Print-Error "Failed to import livekit.agents"
}

try {
    python -c "import googleapiclient" 2>&1 | Out-Null
    Print-Success "Google API client imported successfully"
} catch {
    Print-Error "Failed to import googleapiclient"
}

try {
    python -c "import langfuse" 2>&1 | Out-Null
    Print-Success "Langfuse imported successfully"
} catch {
    Print-Warning "Langfuse not available (optional)"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Print-Success "Setup complete!"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit .env.local with your API keys"
Write-Host "  2. Place Google OAuth credentials (client_secret_*.json) in project root"
Write-Host "  3. Activate virtual environment: venv\Scripts\Activate.ps1"
Write-Host "  4. Run the agent: python agent.py dev"
Write-Host ""
Write-Host "For detailed instructions, see SETUP.md" -ForegroundColor Cyan
Write-Host ""

