#!/bin/bash

# Outbound Caller Agent - Setup Script for macOS/Linux
# This script automates the setup process for a new computer

set -e  # Exit on error

echo "🚀 Outbound Caller Agent - Setup Script"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Check if Git is installed
echo "Checking prerequisites..."
if command -v git &> /dev/null; then
    print_success "Git is installed: $(git --version)"
else
    print_error "Git is not installed. Please install Git first:"
    echo "  macOS: brew install git"
    echo "  Linux: sudo apt-get install git"
    exit 1
fi

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python is installed: $PYTHON_VERSION"
    
    # Check if Python version is 3.11 or higher
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
        print_error "Python 3.11 or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

# Check if pip is installed
if command -v pip3 &> /dev/null; then
    print_success "pip is installed"
else
    print_error "pip3 is not installed. Please install pip first."
    exit 1
fi

echo ""
echo "Setting up virtual environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_warning "Virtual environment already exists. Skipping creation."
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "Installing dependencies..."
if [ -f "requirements.txt" ]; then
    print_info "Installing packages from requirements.txt..."
    pip install -r requirements.txt
    print_success "Dependencies installed"
else
    print_error "requirements.txt not found!"
    exit 1
fi

# Download model files
echo ""
echo "Downloading model files..."
if python3 agent.py download-files 2>/dev/null; then
    print_success "Model files downloaded"
else
    print_warning "Model download command not available or failed (this is okay)"
fi

# Check for LiveKit CLI
echo ""
if command -v lk &> /dev/null; then
    print_success "LiveKit CLI is installed: $(lk --version 2>/dev/null || echo 'installed')"
else
    print_warning "LiveKit CLI is not installed. Installing now..."
    if curl -sSL https://get.livekit.io/cli | bash; then
        print_success "LiveKit CLI installed"
    else
        print_warning "Failed to install LiveKit CLI automatically. Please install manually:"
        echo "  curl -sSL https://get.livekit.io/cli | bash"
    fi
fi

# Check for .env.local
echo ""
if [ -f ".env.local" ]; then
    print_success ".env.local file exists"
else
    print_warning ".env.local file not found!"
    echo ""
    echo "You need to create .env.local with the following required variables:"
    echo ""
    echo "  LIVEKIT_URL=https://your-livekit-url.livekit.cloud"
    echo "  LIVEKIT_API_KEY=your_api_key"
    echo "  LIVEKIT_API_SECRET=your_api_secret"
    echo "  SIP_OUTBOUND_TRUNK_ID=your_trunk_id"
    echo "  OPENAI_API_KEY=your_openai_key (or GROQ_API_KEY)"
    echo "  ELEVEN_API_KEY=your_elevenlabs_key"
    echo "  GOOGLE_SHEET_ID=your_spreadsheet_id"
    echo "  LANGFUSE_PUBLIC_KEY=your_public_key"
    echo "  LANGFUSE_SECRET_KEY=your_secret_key"
    echo ""
    echo "See SETUP.md for the complete list of environment variables."
    echo ""
    read -p "Would you like to create .env.local now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        touch .env.local
        print_success ".env.local file created. Please edit it with your API keys."
    fi
fi

# Check for Google OAuth credentials
echo ""
if ls client_secret_*.json 1> /dev/null 2>&1; then
    print_success "Google OAuth credentials found"
else
    print_warning "Google OAuth credentials (client_secret_*.json) not found!"
    echo "  You'll need to:"
    echo "  1. Go to https://console.cloud.google.com/"
    echo "  2. Enable Google Calendar API and Google Sheets API"
    echo "  3. Create OAuth 2.0 credentials"
    echo "  4. Download as JSON and place in project root"
fi

# Verify installation
echo ""
echo "Verifying installation..."
echo ""

# Test imports
if python3 -c "import livekit.agents" 2>/dev/null; then
    print_success "LiveKit agents module imported successfully"
else
    print_error "Failed to import livekit.agents"
fi

if python3 -c "import googleapiclient" 2>/dev/null; then
    print_success "Google API client imported successfully"
else
    print_error "Failed to import googleapiclient"
fi

if python3 -c "import langfuse" 2>/dev/null; then
    print_success "Langfuse imported successfully"
else
    print_warning "Langfuse not available (optional)"
fi

echo ""
echo "========================================"
print_success "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env.local with your API keys"
echo "  2. Place Google OAuth credentials (client_secret_*.json) in project root"
echo "  3. Activate virtual environment: source venv/bin/activate"
echo "  4. Run the agent: python3 agent.py dev"
echo ""
echo "For detailed instructions, see SETUP.md"
echo ""


