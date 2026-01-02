# How to Start Your Agent Worker

## The Problem
Your dispatch script successfully sends jobs to LiveKit, but **the agent worker must be running** to actually make the calls.

## Solution: Run the Agent Worker

Open a **NEW terminal window** and run:

```bash
cd /Users/papapapa/outboundcaller-1
source venv/bin/activate
python agent.py dev
```

## What You Should See

When the agent worker starts successfully, you'll see logs like:

```
INFO livekit.agents - starting worker {"version": "1.2.18", "rtc-version": "1.0.23"}
INFO livekit.agents - registered worker {"id": "AW_...", "url": "wss://cold-caller-6vmkvmbr.livekit.cloud", ...}
```

## How It Works

1. **Terminal 1**: Run `python agent.py dev` - This starts the agent worker that waits for jobs
2. **Terminal 2**: Run `python dispatch_calls.py` - This dispatches calls from Google Sheets

When you dispatch a call:
- The dispatch script sends a job to LiveKit ✅
- The agent worker picks up the job ✅
- The agent makes the phone call ✅

## Keep Both Running

- **Agent worker** (`python agent.py dev`) must stay running continuously
- **Dispatch script** (`python dispatch_calls.py`) runs when you want to process pending calls

## Troubleshooting

If the agent doesn't pick up jobs:
1. Check agent name matches: `outbound-caller-dev`
2. Check `.env.local` has correct `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
3. Make sure `SIP_OUTBOUND_TRUNK_ID` is set in `.env.local`
4. Check agent logs for errors


