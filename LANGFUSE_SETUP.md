# Langfuse Setup Guide

## Overview

Langfuse is already integrated into your AI assistant! It tracks:
- Call start/end events
- Function calls (schedule_meeting, checkAvailability, etc.)
- Call outcomes and metadata
- Transcripts and conversation data

## Quick Setup

### 1. Get Your Langfuse API Keys

1. Go to [https://cloud.langfuse.com](https://cloud.langfuse.com) (or your self-hosted instance)
2. Sign up or log in
3. Go to **Settings** → **API Keys**
4. Create a new API key or use an existing one
5. Copy your **Public Key** and **Secret Key**

### 2. Add to `.env.local`

Add these environment variables:

```bash
# Langfuse Configuration
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxxx

# Optional: If using self-hosted Langfuse
# LANGFUSE_HOST=https://your-langfuse-instance.com
```

### 3. Verify Installation

Langfuse is already in `requirements.txt`. If you need to install it:

```bash
pip install langfuse>=2.0.0
```

### 4. Test It

Run your agent and check the logs:

```bash
./venv/bin/python agent.py dev
```

You should see:
```
✅ Langfuse initialized for observability
📊 Langfuse trace initialized: <trace-id>
```

## What Gets Tracked

### 1. **Call Traces**
- Each call gets a unique trace ID
- Tracks entire call lifecycle
- Includes customer name, phone number, appointment time

### 2. **Events**
- `call_started` - When call begins
- `call_completed` - When call ends
- Includes metadata: status, duration, appointment scheduled

### 3. **Spans (Function Calls)**
- `schedule_meeting` - Appointment scheduling attempts
- `checkAvailability` - Calendar availability checks
- `detected_answering_machine` - Voicemail detection
- `end_call` - Call termination
- `send_sms` - SMS sending (if used)

### 4. **Metadata**
- Call duration
- Appointment scheduled (yes/no)
- Appointment time and email
- Call status (completed, voicemail, no_answer, etc.)
- Transcript length

## Viewing Your Data

### In Langfuse Dashboard

1. Go to your Langfuse dashboard
2. Navigate to **Traces** or **Sessions**
3. Filter by:
   - User ID (phone number)
   - Date range
   - Call status
   - Appointment scheduled

### Key Metrics to Track

- **Call Success Rate**: Completed calls / Total calls
- **Appointment Conversion**: Appointments scheduled / Calls completed
- **Average Call Duration**: Total duration / Number of calls
- **Function Call Success**: Successful function calls / Total attempts

## Advanced Features

### Custom Metadata

You can add custom metadata to traces by modifying `_init_langfuse_trace()` in `agent.py`:

```python
self.langfuse_trace = langfuse.trace(
    name="outbound_call",
    id=self.trace_id,
    metadata={
        "customer_name": self.name,
        "phone_number": self.dial_info.get("phone_number", "unknown"),
        "appointment_time": self.appointment_time,
        "custom_field": "custom_value",  # Add your custom fields
    },
    user_id=self.dial_info.get("phone_number", "unknown"),
)
```

### Exporting Data

Langfuse provides APIs to export your data:

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key="pk-lf-...",
    secret_key="sk-lf-..."
)

# Get traces
traces = langfuse.fetch_traces(limit=100)
```

## Troubleshooting

### "Langfuse keys not found"
- Check that `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set in `.env.local`
- Make sure you're loading `.env.local` (it should be automatic)

### "Failed to initialize Langfuse"
- Verify your API keys are correct
- Check your internet connection
- If using self-hosted, verify `LANGFUSE_HOST` is correct

### No data appearing in dashboard
- Wait a few seconds - data is sent asynchronously
- Check that calls are actually being made
- Verify API keys have write permissions

### "Langfuse not available"
- Install: `pip install langfuse>=2.0.0`
- Restart your agent after installing

## Current Integration Status

✅ **Already Implemented:**
- Trace initialization per call
- Call start/end events
- Function call spans (schedule_meeting, checkAvailability, etc.)
- Call metadata (duration, status, appointment info)
- Error logging

🔄 **Can Be Enhanced:**
- LLM input/output tracking (if using OpenAI/Groq directly)
- Token usage tracking
- Response time metrics
- Custom business metrics

## Next Steps

1. **Set up your API keys** in `.env.local`
2. **Make a test call** to see data appear
3. **Explore the dashboard** to understand your call patterns
4. **Set up alerts** in Langfuse for failed calls or low conversion rates

## Support

- Langfuse Docs: https://langfuse.com/docs
- Langfuse Discord: https://discord.gg/langfuse
- Your agent logs will show Langfuse status on startup


