# Langfuse Quick Start

## Your API Keys

Add these to your `.env.local` file:

```bash
LANGFUSE_PUBLIC_KEY="pk-lf-fc497d84-a162-45ab-8086-888e1d2407c5"
LANGFUSE_SECRET_KEY="sk-lf-2df46a66-8eb5-43bb-8cbb-e06a7f406a5e"
LANGFUSE_BASE_URL="https://cloud.langfuse.com"
```

**Note:** The code supports both `LANGFUSE_HOST` and `LANGFUSE_BASE_URL` - either one works!

## Verify It's Working

1. **Add the keys to `.env.local`** (if not already there)

2. **Restart your agent:**
   ```bash
   ./venv/bin/python agent.py dev
   ```

3. **Look for this in the logs:**
   ```
   ✅ Langfuse initialized for observability
   📊 Langfuse trace initialized: <trace-id>
   ```

4. **Make a test call** and check your Langfuse dashboard at https://cloud.langfuse.com

## What You'll See in Langfuse

- **Traces**: Each call gets a unique trace
- **Events**: Call started, call completed
- **Spans**: Function calls (schedule_meeting, checkAvailability, etc.)
- **Metadata**: Call duration, status, appointment info

## View Your Data

1. Go to https://cloud.langfuse.com
2. Navigate to **Traces** or **Sessions**
3. Filter by phone number, date, or status
4. Click on any trace to see full call details

## Troubleshooting

**"Langfuse keys not found"**
- Make sure keys are in `.env.local` (not `.env`)
- Restart the agent after adding keys

**"Failed to initialize Langfuse"**
- Check your internet connection
- Verify API keys are correct
- Check that `LANGFUSE_BASE_URL` matches your Langfuse instance

**No data appearing**
- Wait a few seconds - data is sent asynchronously
- Make sure calls are actually being made
- Check agent logs for Langfuse errors

## Ready to Go!

Once you add the keys and restart, Langfuse will automatically start tracking all your calls! 🚀

