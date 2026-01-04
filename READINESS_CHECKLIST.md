# Agent Readiness Checklist

## ✅ Code Status
- All Python files compile successfully ✓
- No syntax errors ✓
- Recent improvements implemented:
  - Voicemail detection and auto-move to next call ✓
  - Transcript capture (user + AI) ✓
  - Call duration formatting fixed ✓
  - Silence timeout for no response ✓
  - Proper call status tracking (Hung Up vs No Answer) ✓

## 🔧 Required Environment Variables

### **Critical (Must Have)**
1. **LIVEKIT_URL** - Your LiveKit Cloud URL (e.g., `https://your-project.livekit.cloud`)
2. **LIVEKIT_API_KEY** - LiveKit API key
3. **LIVEKIT_API_SECRET** - LiveKit API secret
4. **SIP_OUTBOUND_TRUNK_ID** - Your LiveKit SIP trunk ID
5. **OPENAI_API_KEY** - OpenAI API key (for LLM)
6. **ELEVEN_API_KEY** or **ELEVENLABS_API_KEY** - ElevenLabs API key (for TTS)
7. **ELEVENLABS_VOICE_ID** - Your ElevenLabs voice ID
8. **GOOGLE_SHEET_ID** - Your Google Sheet ID
9. **GOOGLE_SHEET_NAME** - Sheet name (usually "Sheet1")

### **Optional but Recommended**
- **LLM_PROVIDER** - `openai`, `openai-realtime`, or `groq` (default: `groq`)
- **OPENAI_MODEL** - Model name (default: `gpt-4o-mini`)
- **TTS_SPEED** - Voice speed 0.7-1.2 (default: `1.0`)
- **NO_RESPONSE_TIMEOUT** - Seconds to wait for user response (default: `10.0`)
- **DEEPGRAM_API_KEY** - Only needed if using Deepgram STT (not needed for OpenAI Realtime)

### **For Cloud Deployment**
- **GOOGLE_CALENDAR_TOKEN_JSON** - Base64 encoded Google Calendar token (or use local `token.json`)
- **GOOGLE_CALENDAR_CREDENTIALS_JSON** - Base64 encoded Google Calendar credentials (or use local `credentials.json`)
- **GOOGLE_SHEETS_TOKEN_JSON** - Base64 encoded Google Sheets token (or use local `google_sheets_token.json`)

### **Optional Observability**
- **LANGFUSE_PUBLIC_KEY** - For call analytics (optional)
- **LANGFUSE_SECRET_KEY** - For call analytics (optional)

## 📋 Google Sheet Setup

### Required Columns (in order):
1. **Phone_number** - Phone number with country code (e.g., `+12095539289`)
2. **Name** - Customer name
3. **Status** - Will be auto-updated (Pending → Dispatched → Completed/Voicemail/etc.)

### Recommended Additional Columns:
4. **Call Start Time** - Auto-populated
5. **Call End Time** - Auto-populated
6. **Call Duration** - Auto-populated (formatted as "2m 30s")
7. **Outcome Details** - Auto-populated (e.g., "Appointment Scheduled", "Voicemail - Left Message")
8. **Appointment Scheduled** - Auto-populated (Yes/No)
9. **Appointment Time Scheduled** - Auto-populated
10. **Appointment Email** - Auto-populated
11. **Transcript** - Auto-populated
12. **Last Called** - Auto-populated

## 🚀 Pre-Launch Checklist

### 1. Environment Variables
- [ ] All critical environment variables set in `.env.local`
- [ ] API keys are valid and have sufficient quota
- [ ] ElevenLabs voice ID is correct and accessible
- [ ] Google Sheet ID and name are correct

### 2. Google OAuth Setup
- [ ] Google Calendar OAuth token (`token.json`) exists OR `GOOGLE_CALENDAR_TOKEN_JSON` env var set
- [ ] Google Calendar credentials (`credentials.json`) exists OR `GOOGLE_CALENDAR_CREDENTIALS_JSON` env var set
- [ ] Google Sheets OAuth token (`google_sheets_token.json`) exists OR `GOOGLE_SHEETS_TOKEN_JSON` env var set
- [ ] OAuth tokens are not expired

### 3. LiveKit Setup
- [ ] SIP outbound trunk is configured in LiveKit Cloud
- [ ] SIP trunk ID matches `SIP_OUTBOUND_TRUNK_ID` in `.env.local`
- [ ] Agent is deployed to LiveKit Cloud OR running locally with `python agent.py dev`

### 4. Google Sheet
- [ ] Sheet has required columns (Phone_number, Name, Status)
- [ ] At least one row with `Status = "Pending"` for testing
- [ ] Phone numbers are in E.164 format (`+1234567890`)

### 5. Testing
- [ ] Test a single call: `./venv/bin/python dispatch_calls.py`
- [ ] Verify call connects and agent speaks
- [ ] Verify transcript is saved to Google Sheet
- [ ] Verify voicemail detection works
- [ ] Verify appointment scheduling works (if applicable)

## 🐛 Common Issues to Check

1. **"No Answer" when user hung up**: Fixed - now shows "Hung Up" ✓
2. **Call Duration showing timestamp**: Fixed - now shows "2m 30s" format ✓
3. **Transcript not saving**: Fixed - now captures both user and AI speech ✓
4. **Voicemail not moving to next call**: Fixed - automatically moves to next call ✓

## 📝 Notes

- The agent will automatically:
  - Hang up on voicemail and move to next call
  - Save transcripts to Google Sheets
  - Track call duration and status
  - Schedule appointments via Google Calendar
  - Handle silence timeout (hangs up if no response after greeting)

- For cloud deployment, make sure to set the Google OAuth environment variables instead of using local files.

## ✅ Ready to Go!

If all items above are checked, your agent is ready for production use!

