# Quick Start Checklist

## ❌ Does it work out of the box?
**No** - You need to configure API keys and environment variables first.

## ✅ What You Already Have Set Up

- ✓ Python virtual environment (`venv`)
- ✓ Google Calendar credentials (`credentials.json`)
- ✓ Google Calendar authentication (`token.json`)
- ✓ Dependencies installed (from `requirements.txt`)

## 🔧 What You Need to Configure

### 1. Required Environment Variables

Create or update `.env.local` with these **required** variables:

```bash
# LiveKit Configuration (REQUIRED)
LIVEKIT_URL=wss://your-livekit-server.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
SIP_OUTBOUND_TRUNK_ID=your_sip_trunk_id

# ElevenLabs TTS (REQUIRED - agent uses this for voice)
ELEVEN_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=U1xXYn8cDFT02st4a5oq  # Optional - has default
```

### 2. LLM Provider (Choose One)

```bash
# Option A: Groq (Free tier, but has rate limits)
GROQ_API_KEY=your_groq_api_key
LLM_PROVIDER=groq

# Option B: OpenAI (Recommended - better rate limits)
OPENAI_API_KEY=your_openai_api_key
LLM_PROVIDER=openai
```

### 3. STT Provider (Optional - has defaults)

```bash
# Optional: Deepgram for speech-to-text
DEEPGRAM_API_KEY=your_deepgram_api_key
```

### 4. Google Sheets (Optional - for dispatching calls)

```bash
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_SHEET_NAME=Sheet1
```

## 🚀 Quick Test

Once configured, test if everything works:

### Step 1: Test Google Calendar
```bash
python test_google_auth.py
```
Should show: ✅ Authentication successful

### Step 2: Run the Agent
```bash
source venv/bin/activate
python agent.py dev
```

You should see:
- Agent connecting to LiveKit
- Waiting for dispatches
- No errors about missing API keys

### Step 3: Test a Call (Optional)
```bash
python dispatch_calls.py
```

## ❌ Common Issues

1. **"API key not found"** → Add the missing key to `.env.local`
2. **"Credentials not found"** → You already have `credentials.json`, should be fine
3. **"Cannot connect to LiveKit"** → Check `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
4. **"ElevenLabs voice not working"** → Check `ELEVEN_API_KEY` and that the voice ID is in your account

## 📋 Minimum Setup to Make a Call

**Absolute minimum** to make a test call:

1. ✓ Install dependencies: `pip install -r requirements.txt`
2. ✓ Set LiveKit credentials (URL, API_KEY, API_SECRET, SIP_OUTBOUND_TRUNK_ID)
3. ✓ Set ElevenLabs API key (`ELEVEN_API_KEY`)
4. ✓ Set one LLM provider (`OPENAI_API_KEY` OR `GROQ_API_KEY` with `LLM_PROVIDER=groq`)

**For full functionality:**
- Add Google Sheets config (for `dispatch_calls.py`)
- Google Calendar already works (you have credentials)

## 🎯 Next Steps After Setup

1. ✅ Configure environment variables
2. ✅ Test Google Calendar: `python test_google_auth.py`
3. ✅ Run agent: `python agent.py dev`
4. ✅ Test dispatch: `python dispatch_calls.py` (if using Google Sheets)
5. ✅ Make a test call and verify everything works

---

**TL;DR**: No, it doesn't work out of the box. You need to set up API keys in `.env.local`, but the Google Calendar integration is already configured!


