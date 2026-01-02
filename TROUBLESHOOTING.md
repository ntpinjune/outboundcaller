# Troubleshooting: Agent Deployed But Not Making Calls

## Quick Checklist

### 1. Check Agent Logs in LiveKit Cloud

1. Go to LiveKit Cloud Dashboard
2. Navigate to: **Agents** → **CA_ERnckSYLUAYN** (your agent)
3. Click on **Logs** tab
4. Look for:
   - ✅ `connecting to room` - Agent received the job
   - ✅ `participant joined` - Call connected
   - ❌ Any error messages

**What to look for:**
- If you see `connecting to room` → Agent is receiving jobs ✅
- If you see errors about `SIP_OUTBOUND_TRUNK_ID` → Missing SIP trunk config
- If you see errors about API keys → Missing environment variables
- If you see nothing → Job might not be reaching the agent

### 2. Verify Environment Variables in Cloud

In LiveKit Cloud Dashboard → Your Agent → Settings → Environment Variables, make sure you have:

**REQUIRED:**
```
SIP_OUTBOUND_TRUNK_ID=ST_jXCZwUp859wY
LIVEKIT_URL=wss://cold-caller-6vmkvmbr.livekit.cloud
LIVEKIT_API_KEY=APIkzg3gFyEDWWG
LIVEKIT_API_SECRET=1CuQUimQvp8JJO3vv6fsZ3BetuaKxkVWZMUwPyNgQg8
```

**API Keys (at least one set):**
```
OPENAI_API_KEY=your_key (if using OpenAI)
GROQ_API_KEY=your_key (if using Groq)
DEEPGRAM_API_KEY=your_key (required for STT)
CARTESIA_API_KEY=your_key (required for TTS)
```

**Optional:**
```
LLM_PROVIDER=groq (or openai)
MAKE_COM_WEBHOOK_URL=your_webhook
MAKE_COM_CALL_RESULTS_WEBHOOK_URL=your_webhook
```

### 3. Test Dispatch Again

Run your dispatch script and watch the agent logs in real-time:

```bash
# Terminal 1: Watch agent logs in LiveKit Cloud Dashboard
# Terminal 2: Run dispatch
python dispatch_calls.py
```

### 4. Common Issues

#### Issue: Agent receives job but doesn't dial

**Symptoms:**
- Logs show `connecting to room`
- But no `create_sip_participant` or dialing logs

**Fix:**
- Check `SIP_OUTBOUND_TRUNK_ID` is set correctly
- Verify SIP trunk is active in LiveKit Cloud

#### Issue: "SIP_OUTBOUND_TRUNK_ID not found"

**Fix:**
- Add `SIP_OUTBOUND_TRUNK_ID=ST_jXCZwUp859wY` to environment variables
- Redeploy agent

#### Issue: "API key missing" errors

**Fix:**
- Add required API keys (Deepgram, Cartesia, OpenAI/Groq)
- Redeploy agent

#### Issue: Job created but agent never receives it

**Symptoms:**
- Dispatch script says "Successfully dispatched"
- But agent logs show nothing

**Fix:**
- Verify agent name matches: `outbound-caller-dev`
- Check agent is in same region as your LiveKit project
- Try redeploying the agent

### 5. Test with LiveKit CLI

Test if the agent can receive jobs directly:

```bash
lk dispatch create \
  --new-room \
  --agent-name outbound-caller-dev \
  --metadata '{"phone_number": "+12095539289", "name": "Test", "row_id": "1"}'
```

Then check agent logs to see if it received the job.

### 6. Check SIP Trunk Status

1. Go to LiveKit Cloud Dashboard
2. Navigate to **SIP** → **Trunks**
3. Verify trunk `ST_jXCZwUp859wY` is:
   - ✅ Active
   - ✅ Configured for outbound calls
   - ✅ Has phone number capability

### 7. Debug Steps

1. **Check agent is running**: Dashboard shows "RUNNING" ✅
2. **Check dispatch succeeds**: Script says "Successfully dispatched" ✅
3. **Check agent logs**: Look for `connecting to room` message
4. **Check for errors**: Look for red error messages in logs
5. **Check environment variables**: All required vars are set
6. **Check SIP trunk**: Trunk ID matches and is active

## Next Steps

1. Check agent logs in LiveKit Cloud Dashboard
2. Verify all environment variables are set
3. Test dispatch again and watch logs in real-time
4. Share any error messages you see


