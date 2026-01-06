# Quick Setup Reference

## Automated Setup (Recommended)

**macOS/Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows (PowerShell):**
```powershell
.\setup.ps1
```

## Manual Setup Commands

```bash
# 1. Clone repository
git clone <your-repo-url>
cd outboundcaller-1

# 2. Create virtual environment
python3 -m venv venv

# 3. Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate     # Windows

# 4. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
python agent.py download-files

# 5. Install LiveKit CLI
curl -sSL https://get.livekit.io/cli | bash  # macOS/Linux
# OR
iwr https://get.livekit.io/cli.ps1 -useb | iex  # Windows PowerShell

# 6. Create .env.local file
# Copy the template below and fill in your values
```

## Required Environment Variables (.env.local)

```bash
LIVEKIT_URL=https://your-livekit-url.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
SIP_OUTBOUND_TRUNK_ID=your_trunk_id
OPENAI_API_KEY=your_openai_key
ELEVEN_API_KEY=your_elevenlabs_key
GOOGLE_SHEET_ID=your_spreadsheet_id
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
```

## Run the Agent

```bash
# Activate virtual environment first
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Run agent
python3 agent.py dev

# In another terminal, run dispatch
python3 dispatch_calls.py
# OR parallel dispatch
python3 dispatch_calls_parallel.py
```

## Required Files

- `.env.local` - Environment variables (create this)
- `client_secret_*.json` - Google OAuth credentials (download from Google Cloud Console)
- `token.json` - Auto-generated on first run (Google Calendar)
- `google_sheets_token.json` - Auto-generated on first run (Google Sheets)

## Full Documentation

See `SETUP.md` for complete setup instructions and troubleshooting.

