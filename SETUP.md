# Complete Setup Guide for New Computer

This guide will help you set up the outbound caller agent on a new computer from scratch.

## Prerequisites

### 1. Install Git
**macOS:**
```bash
brew install git
# OR download from https://git-scm.com/download/mac
```

**Windows:**
- Download from [https://git-scm.com/download/win](https://git-scm.com/download/win)
- Run the installer

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install git
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install git
```

### 2. Install Python 3.11 or Higher
**macOS:**
```bash
brew install python3
# OR download from https://www.python.org/downloads/
```

**Windows:**
- Download from [https://www.python.org/downloads/](https://www.python.org/downloads/)
- Make sure to check "Add Python to PATH" during installation

**Linux:**
```bash
# Usually pre-installed, verify with:
python3 --version
# If not installed:
sudo apt-get install python3 python3-pip python3-venv
```

### 3. Install LiveKit CLI
**macOS/Linux:**
```bash
curl -sSL https://get.livekit.io/cli | bash
```

**Windows (PowerShell):**
```powershell
iwr https://get.livekit.io/cli.ps1 -useb | iex
```

## Quick Setup (Automated)

Run the setup script:

**macOS/Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```powershell
.\setup.ps1
```

## Manual Setup Steps

If you prefer to set up manually, follow these steps:

### Step 1: Clone the Repository
```bash
git clone <your-repository-url>
cd outboundcaller-1
```

### Step 2: Create Virtual Environment
```bash
python3 -m venv venv
```

### Step 3: Activate Virtual Environment
**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```powershell
venv\Scripts\activate
```

### Step 4: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
python agent.py download-files
```

### Step 5: Create Environment File
Copy the example and fill in your values:
```bash
cp .env.example .env.local  # If .env.example exists
# OR create .env.local manually
```

### Step 6: Configure Environment Variables
Create/edit `.env.local` with the following required variables:

```bash
# LiveKit Configuration
LIVEKIT_URL=https://your-livekit-url.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# SIP Trunk
SIP_OUTBOUND_TRUNK_ID=your_trunk_id

# LLM Provider (choose one)
OPENAI_API_KEY=your_openai_key
# OR use Groq (default)
GROQ_API_KEY=your_groq_key
LLM_PROVIDER=groq  # or "openai"

# TTS (ElevenLabs)
ELEVEN_API_KEY=your_elevenlabs_key
ELEVENLABS_VOICE_ID=your_voice_id

# STT (Deepgram - optional)
DEEPGRAM_API_KEY=your_deepgram_key

# Google Sheets
GOOGLE_SHEET_ID=your_spreadsheet_id
GOOGLE_SHEET_NAME=Sheet1

# Langfuse (Observability)
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# Optional: Twilio (for SMS)
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_FROM_NUMBER=your_twilio_number

# Optional: Call Settings
CALL_DELAY_SECONDS=5
MAX_CALL_DURATION=300
NO_RESPONSE_TIMEOUT=10.0
MAX_RETRIES=3
RETRY_NO_ANSWER=true

# Optional: Parallel Dialing
MAX_CONCURRENT_CALLS=5
PARALLEL_DIALING_ENABLED=true
CALL_START_DELAY=0.5

# Optional: Agent Settings
USE_LOCAL_AGENT=false
TTS_SPEED=1.0
INITIAL_GREETING_DELAY=1.0
```

### Step 7: Set Up Google OAuth Credentials

You need these files in the project root:

1. **`client_secret_*.json`** - Google OAuth client secret (for Google Calendar)
   - Get from [Google Cloud Console](https://console.cloud.google.com/)
   - Enable Google Calendar API and Google Sheets API
   - Create OAuth 2.0 credentials
   - Download as JSON and place in project root

2. **`token.json`** - Auto-generated on first run (for Google Calendar)
   - The script will prompt you to authenticate in a browser on first run

3. **`google_sheets_token.json`** - Auto-generated on first run (for Google Sheets)
   - The script will prompt you to authenticate in a browser on first run

**To get Google OAuth credentials:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable **Google Calendar API** and **Google Sheets API**
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Choose "Desktop app" as application type
6. Download the JSON file and rename it to `client_secret_*.json` (or keep original name)
7. Place it in the project root directory

### Step 8: Verify Setup
```bash
# Check Python version (should be 3.11+)
python3 --version

# Check if virtual environment is active (should show venv path)
which python3  # macOS/Linux
where python3  # Windows

# Test that dependencies are installed
python3 -c "import livekit.agents; print('✅ LiveKit installed')"
python3 -c "import googleapiclient; print('✅ Google API installed')"
python3 -c "import langfuse; print('✅ Langfuse installed')"

# Test LiveKit CLI
lk --version
```

### Step 9: Run the Agent
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Run the agent
python3 agent.py dev
```

### Step 10: Run Dispatch Script (in another terminal)
```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Run dispatch (sequential)
python3 dispatch_calls.py

# OR run parallel dispatch
python3 dispatch_calls_parallel.py
```

## Setup Checklist

Use this checklist to ensure everything is set up correctly:

- [ ] Git installed (`git --version`)
- [ ] Python 3.11+ installed (`python3 --version`)
- [ ] Repository cloned
- [ ] Virtual environment created (`python3 -m venv venv`)
- [ ] Virtual environment activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Model files downloaded (`python agent.py download-files`)
- [ ] LiveKit CLI installed (`lk --version`)
- [ ] `.env.local` file created with all API keys
- [ ] Google OAuth credentials (`client_secret_*.json`) in place
- [ ] Google authentication completed (will generate `token.json` and `google_sheets_token.json` on first run)
- [ ] Agent tested (`python3 agent.py dev`)
- [ ] Dispatch script tested

## Troubleshooting

### Python not found
- Make sure Python 3.11+ is installed
- On macOS, you may need to use `python3` instead of `python`
- On Windows, make sure Python was added to PATH during installation

### Virtual environment not activating
- Make sure you're in the project directory
- Try recreating the venv: `rm -rf venv && python3 -m venv venv`
- On Windows, use `venv\Scripts\activate` (backslash, not forward slash)

### Missing dependencies
- Make sure virtual environment is activated
- Try: `pip install --upgrade pip` then `pip install -r requirements.txt`

### Google OAuth errors
- Make sure `client_secret_*.json` is in the project root
- Make sure Google Calendar API and Google Sheets API are enabled in Google Cloud Console
- Delete `token.json` and `google_sheets_token.json` and re-authenticate

### LiveKit connection errors
- Verify `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in `.env.local`
- Make sure the URL uses `https://` not `wss://`

### Missing API keys
- Check that all required keys are in `.env.local`
- Make sure `.env.local` is in the project root (not in a subdirectory)

## Next Steps

After setup is complete:

1. **Test the agent locally:**
   ```bash
   python3 agent.py dev
   ```

2. **Test Google Sheets connection:**
   - Run `python3 dispatch_calls.py` to see if it can read from your Google Sheet

3. **Test a single call:**
   - Use LiveKit CLI to dispatch a test call:
   ```bash
   lk dispatch create \
     --new-room \
     --agent-name outbound-caller-dev \
     --metadata '{"phone_number": "+1234567890", "name": "Test User"}'
   ```

4. **Monitor with Langfuse:**
   - Visit your Langfuse dashboard to see agent traces and metrics

## Additional Resources

- [LiveKit Agents Documentation](https://docs.livekit.io/agents/overview/)
- [Google Cloud Console](https://console.cloud.google.com/)
- [LiveKit Cloud](https://livekit.io/cloud)
- [Langfuse Documentation](https://langfuse.com/docs)


