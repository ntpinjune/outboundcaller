# Deploy Agent to LiveKit Cloud

## Why Deploy to Cloud?

✅ **More Reliable** - Runs 24/7, no need to keep your computer on  
✅ **Auto-scaling** - Handles multiple calls automatically  
✅ **No Local Setup** - No need to run `python agent.py dev` locally  
✅ **Better Performance** - Runs on LiveKit's infrastructure  

## Prerequisites

You already have:
- ✅ `livekit.toml` configured with your project
- ✅ Agent ID: `CA_ERnckSYLUAYN`
- ✅ Dockerfile ready

## Option 1: Deploy via LiveKit CLI (Easiest)

### Step 1: Install LiveKit CLI

```bash
# macOS
brew install livekit/tap/livekit

# Or download from: https://github.com/livekit/livekit-cli/releases
```

### Step 2: Authenticate with LiveKit Cloud

```bash
lk cloud auth
```

This will link your LiveKit Cloud project to the CLI.

### Step 3: Navigate to Your Project

```bash
cd /Users/papapapa/outboundcaller-1
```

### Step 4: Deploy Your Agent

```bash
lk agent create
```

This will:
- Register your agent with LiveKit Cloud
- Build and deploy your Docker image
- Set up the agent to run continuously

**OR** if you already have an agent ID configured in `livekit.toml`:

```bash
lk agent deploy
```

### Step 5: Verify Deployment

Check your agent status in the LiveKit Cloud dashboard or:

```bash
lk agent list
```

You should see your agent `outbound-caller-dev` running.

## Option 2: Deploy via LiveKit Cloud Dashboard

1. Go to [LiveKit Cloud Dashboard](https://cloud.livekit.io/)
2. Navigate to your project: `cold-caller-6vmkvmbr`
3. Go to **Agents** section
4. Click **Deploy Agent**
5. Upload your Dockerfile or connect a Git repository
6. Configure:
   - **Agent Name**: `outbound-caller-dev`
   - **Environment Variables**: Copy from `.env.local`
   - **Resources**: Adjust CPU/Memory as needed

## Environment Variables for Cloud

Make sure these are set in LiveKit Cloud dashboard:

```
LIVEKIT_URL=wss://cold-caller-6vmkvmbr.livekit.cloud
LIVEKIT_API_KEY=APIkzg3gFyEDWWG
LIVEKIT_API_SECRET=1CuQUimQvp8JJO3vv6fsZ3BetuaKxkVWZMUwPyNgQg8
SIP_OUTBOUND_TRUNK_ID=ST_jXCZwUp859wY
OPENAI_API_KEY=your_openai_key
DEEPGRAM_API_KEY=your_deepgram_key
CARTESIA_API_KEY=your_cartesia_key
GROQ_API_KEY=your_groq_key (if using Groq)
MAKE_COM_WEBHOOK_URL=your_make_webhook_url
MAKE_COM_CALL_RESULTS_WEBHOOK_URL=your_results_webhook_url
LLM_PROVIDER=groq (or openai)
```

## After Deployment

Once deployed, your agent will:
- ✅ Run continuously in the cloud
- ✅ Automatically pick up jobs when you dispatch calls
- ✅ Scale up/down based on demand
- ✅ No need to run `python agent.py dev` locally

## Test It

1. Deploy agent to cloud (using one of the methods above)
2. Run your dispatch script locally:
   ```bash
   python dispatch_calls.py
   ```
3. The cloud agent will pick up the job and make the call!

## Troubleshooting

### Agent Not Picking Up Jobs

1. Check agent is running: `lk agent list`
2. Verify agent name matches: `outbound-caller-dev`
3. Check agent logs in LiveKit Cloud dashboard
4. Verify environment variables are set correctly

### Deployment Fails

1. Check Dockerfile is valid: `docker build -t test .`
2. Verify `livekit.toml` has correct project/agent ID
3. Check you're logged in: `lk whoami`

## Local vs Cloud

| Feature | Local (`python agent.py dev`) | Cloud (Deployed) |
|---------|------------------------------|------------------|
| Reliability | ❌ Stops if computer sleeps | ✅ Runs 24/7 |
| Setup | ✅ Quick to start | ⚠️ One-time setup |
| Cost | ✅ Free | 💰 Pay per usage |
| Scaling | ❌ Single instance | ✅ Auto-scales |
| Maintenance | ❌ Manual restart | ✅ Managed |

**Recommendation**: Deploy to cloud for production use!

