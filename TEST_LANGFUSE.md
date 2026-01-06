# Testing Langfuse Integration

## Quick Test Steps

### 1. Verify Environment Variables

Your `.env.local` should have:
```bash
LANGFUSE_PUBLIC_KEY="pk-lf-fc497d84-a162-45ab-8086-888e1d2407c5"
LANGFUSE_SECRET_KEY="sk-lf-2df46a66-8eb5-43bb-8cbb-e06a7f406a5e"
LANGFUSE_BASE_URL="https://cloud.langfuse.com"
```

✅ These are already set!

### 2. Start Your Agent

```bash
./venv/bin/python agent.py dev
```

**Look for this in the logs:**
```
✅ Langfuse OpenTelemetry tracing enabled for LiveKit Agents
```

If you see this, Langfuse is configured correctly!

### 3. Make a Test Call

**Option A: Use dispatch script (recommended)**
1. Add a test row to your Google Sheet:
   - Phone_number: Your phone number (e.g., `+1234567890`)
   - Name: Test
   - Status: `Pending`

2. Run dispatch:
   ```bash
   ./venv/bin/python dispatch_calls.py
   ```

**Option B: Use LiveKit CLI directly**
```bash
lk dispatch create \
  --new-room \
  --agent-name outbound-caller-dev \
  --metadata '{"phone_number": "+YOUR_PHONE_NUMBER", "name": "Test User"}'
```

### 4. Check Langfuse Dashboard

1. **Go to**: https://cloud.langfuse.com
2. **Navigate to your project** (the one matching your API keys)
3. **Click on "Traces"** in the sidebar
4. **Look for traces** - you should see:
   - Trace name: Something like "session" or "outbound_call"
   - Spans for: Session start, Agent turn, LLM node, Function tools, TTS node
   - Metadata: Phone number, customer name, etc.

### 5. What to Look For

**Successful Integration Shows:**
- ✅ Traces appear within 10-30 seconds after call ends
- ✅ Multiple spans (Session, Agent Turn, LLM, Functions, TTS)
- ✅ Metadata with phone number and customer name
- ✅ Function call spans (schedule_meeting, checkAvailability, etc.)
- ✅ Duration and timing information

**If No Traces Appear:**
- Check agent logs for "✅ Langfuse OpenTelemetry tracing enabled"
- Verify API keys are correct in `.env.local`
- Check network connectivity to Langfuse
- Wait 30-60 seconds (traces are sent asynchronously)

### 6. View Trace Details

Click on any trace to see:
- **Timeline**: Visual timeline of all spans
- **Spans**: Detailed view of each operation
- **Metadata**: Call information (phone, name, etc.)
- **Function Calls**: Tools that were called
- **LLM Interactions**: Input/output for each LLM call

## Troubleshooting

### "Langfuse OpenTelemetry tracing enabled" not in logs
- Check that packages are installed: `./venv/bin/pip list | grep langfuse`
- Verify environment variables are loaded
- Check for import errors in logs

### Traces appear but are empty
- This is normal - LiveKit sends traces asynchronously
- Wait a few seconds and refresh
- Check that the call actually completed

### No traces at all
- Verify API keys match the project you're viewing
- Check that `LANGFUSE_BASE_URL` is correct
- Look for errors in agent logs
- Try making another call

## Expected Trace Structure

```
Trace: <session-id>
├── Session Start
├── Agent Turn 1
│   ├── LLM Node
│   ├── Function Tool: checkAvailability (if called)
│   └── TTS Node
├── Agent Turn 2
│   ├── LLM Node
│   ├── Function Tool: schedule_meeting (if called)
│   └── TTS Node
└── Session End
```

## Next Steps

Once you see traces:
1. **Explore the dashboard** - Check different views (Traces, Sessions, Metrics)
2. **Set up alerts** - Get notified of failed calls or errors
3. **Create dashboards** - Track key metrics (call duration, success rate, etc.)
4. **Add custom metadata** - Enhance traces with business-specific data

## Quick Verification Command

Run this to verify everything is set up:
```bash
./venv/bin/python -c "
from dotenv import load_dotenv
import os
load_dotenv('.env.local')
print('✅ Public Key:', 'SET' if os.getenv('LANGFUSE_PUBLIC_KEY') else 'NOT SET')
print('✅ Secret Key:', 'SET' if os.getenv('LANGFUSE_SECRET_KEY') else 'NOT SET')
print('✅ Base URL:', os.getenv('LANGFUSE_BASE_URL', 'NOT SET'))
"
```


