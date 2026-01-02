# How to Force Local Agent (Not Cloud)

## The Problem

LiveKit routes jobs to **ANY available agent** with the matching name. If both cloud and local agents are running, LiveKit might pick either one.

## Solution: Stop Cloud Agent

### Step 1: Stop Cloud Agent in LiveKit Dashboard

1. Go to [LiveKit Cloud Dashboard](https://cloud.livekit.io/)
2. Navigate to: **Agents** → **CA_ERnckSYLUAYN** (your agent)
3. Click **Stop** or **Delete** the cloud agent
4. **OR** set it to **Inactive/Disabled**

**Important:** Only ONE agent should be running at a time!

### Step 2: Verify Local Agent is Running

In Terminal 1, make sure you see:

```bash
python agent.py dev
```

**Expected output:**
```
INFO livekit.agents - starting worker
INFO livekit.agents - registered worker {"id": "AW_...", ...}
```

If you see "registered worker", your local agent is connected and ready.

### Step 3: Dispatch to Local Agent

In Terminal 2:

```bash
python dispatch_calls.py
```

**Now it will use your local agent** because it's the only one running!

## How LiveKit Routing Works

```
Dispatch Script
    ↓
Sends job to LiveKit Cloud
    ↓
LiveKit Cloud checks: "Who has agent_name='outbound-caller-dev'?"
    ↓
If BOTH cloud and local are running → Might pick either ❌
If ONLY local is running → Picks local ✅
If ONLY cloud is running → Picks cloud ✅
```

## Verification

### Check Which Agent Received the Job

**In your local agent terminal**, you should see:
```
INFO - connecting to room ...
INFO - participant joined: +12095539289
```

**If you DON'T see this**, the cloud agent might have picked it up instead.

### Check Agent Status

**Local Agent (Terminal 1):**
- Should show "registered worker"
- Should show "connecting to room" when job arrives

**Cloud Agent (Dashboard):**
- Should be **Stopped** or **Inactive**
- Status should NOT be "RUNNING"

## Quick Checklist

- [ ] Cloud agent is **stopped** in LiveKit Dashboard
- [ ] Local agent is **running** (`python agent.py dev`)
- [ ] Local agent shows "registered worker"
- [ ] Dispatch script runs successfully
- [ ] Local agent terminal shows "connecting to room"

## Alternative: Use Different Agent Names

If you want both running simultaneously, use different agent names:

**Local Agent:**
```python
# In agent.py
agent_name="outbound-caller-local"
```

**Cloud Agent:**
```python
# In cloud deployment
agent_name="outbound-caller-cloud"
```

**Dispatch Script:**
```python
# In dispatch_calls.py
AGENT_NAME = "outbound-caller-local"  # For local
# or
AGENT_NAME = "outbound-caller-cloud"  # For cloud
```

But the **simplest solution** is to just stop the cloud agent when using local! 🎯


