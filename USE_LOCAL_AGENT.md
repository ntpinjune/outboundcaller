# Using Local Agent Instead of Cloud

## Quick Setup

### Step 1: Stop Cloud Agent (Important!)

1. Go to LiveKit Cloud Dashboard
2. Navigate to: **Agents** → **CA_ERnckSYLUAYN**
3. **Stop/Disable** the cloud agent (or delete it temporarily)

This prevents conflicts - you want only ONE agent running.

### Step 2: Start Local Agent

In Terminal 1, run:

```bash
cd /Users/papapapa/outboundcaller-1
source venv/bin/activate
python agent.py dev
```

You should see:
```
INFO livekit.agents - starting worker
INFO livekit.agents - registered worker {"id": "AW_...", ...}
```

**Keep this terminal running!** The agent must stay active to receive jobs.

### Step 3: Configure Dispatch Script

Add to your `.env.local`:

```bash
# Use local agent instead of cloud
USE_LOCAL_AGENT=true
```

### Step 4: Run Dispatch Script

In Terminal 2, run:

```bash
source venv/bin/activate
python dispatch_calls.py
```

The dispatch script will send jobs to LiveKit Cloud, which will route them to your **local agent** (since it's the only one running).

## How It Works

1. **Local Agent** (`python agent.py dev`) connects to LiveKit Cloud and registers as available
2. **Dispatch Script** sends job to LiveKit Cloud
3. **LiveKit Cloud** routes the job to your local agent (since it's registered and available)
4. **Local Agent** picks up the job and makes the call

## Verification

When you run the dispatch script, you should see:
- In Terminal 1 (agent): `connecting to room` → Agent received the job ✅
- In Terminal 2 (dispatch): `✅ Successfully dispatched call` → Job sent ✅

## Switching Back to Cloud

1. Stop local agent (Ctrl+C in Terminal 1)
2. Remove or set `USE_LOCAL_AGENT=false` in `.env.local`
3. Start cloud agent in LiveKit Cloud Dashboard
4. Run dispatch script - it will use cloud agent

## Troubleshooting

### "Agent not receiving jobs"

- ✅ Make sure local agent is running (`python agent.py dev`)
- ✅ Make sure cloud agent is stopped
- ✅ Check agent logs show "registered worker"
- ✅ Verify agent name matches: `outbound-caller-dev`

### "Both agents running"

- ❌ Don't run both at the same time - they'll conflict
- ✅ Stop cloud agent OR stop local agent
- ✅ Only one should be running

### "Local agent not connecting"

- Check `.env.local` has correct `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- Verify you can connect to LiveKit Cloud
- Check agent logs for connection errors


