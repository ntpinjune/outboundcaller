# Call Recording Setup Guide

Your agent now supports automatic call recording using LiveKit's Egress API. Each call will be recorded as an audio file (OGG format) and stored in your cloud storage.

## What Was Changed

1. **Removed `record=True` parameter** from `session.start()` - this was causing errors
2. **Added `start_call_recording()` function** - handles egress recording setup
3. **Integrated recording** into the entrypoint - starts automatically when a call begins

## Configuration

### Option 1: AWS S3 Storage (Recommended)

Add these environment variables to your `.env.local` file:

```bash
# AWS S3 Configuration
AWS_BUCKET_NAME=your-bucket-name
AWS_REGION=us-east-2  # or your preferred region
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Option 2: Google Cloud Storage (GCP)

Add these environment variables to your `.env.local` file:

```bash
# GCP Configuration
GCP_BUCKET_NAME=your-bucket-name
GCP_CREDENTIALS='{"type":"service_account","project_id":"...","private_key":"..."}'  # JSON-encoded service account credentials
```

**Note:** `GCP_CREDENTIALS` should be a JSON-encoded string of your GCP service account credentials. You can get these from the Google Cloud Console.

## How It Works

1. When a call starts, the agent automatically:
   - Checks for AWS or GCP configuration
   - Creates a unique filename: `calls/{phone_number}_{timestamp}.ogg`
   - Starts LiveKit egress recording
   - Records the entire call as audio-only (OGG format)

2. Recording files are stored in your bucket under the `calls/` directory:
   - Example: `calls/12095539289_20241215_143022.ogg`

3. The recording continues until the call ends (when the room closes)

## File Naming

Recordings are named using this format:
```
calls/{phone_number}_{timestamp}.ogg
```

Where:
- `phone_number` = cleaned phone number (no +, spaces, or dashes)
- `timestamp` = `YYYYMMDD_HHMMSS` format

Example: `calls/12095539289_20241215_143022.ogg`

## Troubleshooting

### Recording Not Starting

If you see: `⚠️ No recording storage configured`

**Solution:** Make sure you've set either:
- All AWS variables (`AWS_BUCKET_NAME`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- OR both GCP variables (`GCP_BUCKET_NAME`, `GCP_CREDENTIALS`)

### LiveKit API Errors

If you see: `⚠️ LiveKit credentials not configured`

**Solution:** Make sure these are set in `.env.local`:
```bash
LIVEKIT_URL=https://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
```

### Recording Fails Silently

The agent will log errors but continue with the call. Check your logs for:
- `❌ Failed to start call recording: ...`
- This won't prevent the call from working, but recording won't happen

## Testing

1. Make sure your storage credentials are configured
2. Start your agent: `.\venv\Scripts\python.exe agent.py dev`
3. Dispatch a test call
4. Check your logs for: `✅ Recording started successfully. Egress ID: ...`
5. After the call ends, check your S3/GCP bucket for the recording file

## Notes

- Recordings are **audio-only** (OGG format) - perfect for phone calls
- Each call gets its own file
- Files are automatically uploaded to your cloud storage
- The recording starts when the room connects, before the call is answered
- Recording stops automatically when the call ends
