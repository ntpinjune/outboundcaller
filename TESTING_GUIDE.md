# Testing Guide: Complete System Test

## 🧪 Step-by-Step Testing Instructions

### Prerequisites Check

1. **Google Credentials** - Make sure you have `credentials.json` in project root
2. **Environment Variables** - Check `.env.local` has all required keys
3. **Agent Running** - Either local or cloud agent must be running

---

## 📋 Test 1: Google Calendar Authentication

### Step 1: Test Calendar Access

```bash
cd /Users/papapapa/outboundcaller-1
source venv/bin/activate
python test_google_auth.py
```

**Expected:**
- Browser opens for Google sign-in
- You authorize the app
- Success message appears
- `token.json` file is created

**If it fails:**
- Make sure `credentials.json` exists
- Check you have internet connection
- Verify Google Calendar API is enabled in Google Cloud Console

---

## 📋 Test 2: Google Sheets Authentication

### Step 1: Test Sheets Access

```bash
python dispatch_calls.py
```

**Expected:**
- Browser opens for Google sign-in (first time only)
- You authorize the app
- Script reads from Google Sheets
- `google_sheets_token.json` file is created

**If it fails:**
- Make sure `credentials.json` exists
- Check Google Sheets API is enabled in Google Cloud Console

---

## 📋 Test 3: Full End-to-End Test

### Step 1: Prepare Google Sheet

Add a test row to your Google Sheet:

| Phone_number | Name | Status | Appointment_time |
|--------------|------|--------|------------------|
| +12095539289 | Test User | Pending | |

**Important:**
- Phone number must have `+` prefix
- Status must be exactly `Pending` (case-sensitive)

### Step 2: Start Local Agent (Terminal 1)

```bash
cd /Users/papapapa/outboundcaller-1
source venv/bin/activate
python agent.py dev
```

**Expected Output:**
```
INFO livekit.agents - starting worker
INFO livekit.agents - registered worker {"id": "AW_...", ...}
```

**Keep this terminal running!** The agent must stay active.

### Step 3: Run Dispatch Script (Terminal 2)

Open a **new terminal** and run:

```bash
cd /Users/papapapa/outboundcaller-1
source venv/bin/activate
python dispatch_calls.py
```

**Expected Output:**
```
============================================================
LiveKit Call Dispatcher
============================================================
✓ Google Sheets authentication successful
Reading pending rows from sheet: 1hpr2PnycZIhXSBuzKFTyiLBpivgP5oq3sD1bf3vwcQU
Found 1 pending rows
Starting to process 1 calls...
[1/1] Processing call to +12095539289 (Row 2)...
✅ Successfully dispatched call to +12095539289
```

### Step 4: Watch Agent Logs (Terminal 1)

In the agent terminal, you should see:

```
INFO - connecting to room ...
INFO - participant joined: +12095539289
INFO - (conversation starts)
```

### Step 5: Test Appointment Scheduling

**During the call**, say:
- "I want to schedule an appointment"
- Agent will ask for your email
- Agent will ask for time (e.g., "tomorrow at 2pm")
- Agent will create Google Calendar event

**Check:**
1. Your Google Calendar - should see new event
2. Your email - should receive calendar invite
3. Google Meet link - should be in the event

### Step 6: End Call

Say "goodbye" or let the agent end the call naturally.

**Check Agent Logs:**
```
INFO - Call results updated in Google Sheets: completed
```

### Step 7: Verify Google Sheet Update

Check your Google Sheet - the row should now have:

| Phone_number | Name | Status | Transcript | Call Duration | Appointment Scheduled | Appointment Time Scheduled |
|--------------|------|--------|------------|---------------|----------------------|--------------------------|
| +12095539289 | Test User | Completed | (full transcript) | 120 seconds | Yes | 2025-01-01T14:00:00 |

---

## 🔍 Troubleshooting

### Agent Not Receiving Jobs

**Symptoms:**
- Dispatch says "Successfully dispatched"
- But agent logs show nothing

**Fix:**
1. Check agent is running: `python agent.py dev`
2. Check agent name matches: `outbound-caller-dev`
3. Check `.env.local` has correct `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

### Google Calendar Not Working

**Symptoms:**
- Agent says "scheduling appointment"
- But no calendar event created

**Fix:**
1. Run `python test_google_auth.py` to test authentication
2. Check `token.json` exists
3. Check `credentials.json` is valid
4. Verify Google Calendar API is enabled

### Google Sheets Not Updating

**Symptoms:**
- Call completes
- But sheet doesn't update

**Fix:**
1. Check `google_sheets_token.json` exists
2. Run `python dispatch_calls.py` to test sheets access
3. Verify sheet ID and name are correct in `.env.local`
4. Check column names match (Status, Transcript, etc.)

### Call Not Connecting

**Symptoms:**
- Agent receives job
- But phone doesn't ring

**Fix:**
1. Check `SIP_OUTBOUND_TRUNK_ID` is set in `.env.local`
2. Verify SIP trunk is active in LiveKit Cloud
3. Check phone number format (must have `+` prefix)
4. Check agent logs for SIP errors

---

## ✅ Success Checklist

After testing, you should have:

- [ ] Google Calendar authentication working (`token.json` created)
- [ ] Google Sheets authentication working (`google_sheets_token.json` created)
- [ ] Agent running and receiving jobs
- [ ] Dispatch script reading from Google Sheets
- [ ] Calls being made successfully
- [ ] Appointments being created in Google Calendar
- [ ] Email invites being sent automatically
- [ ] Google Sheets being updated with call results

---

## 🚀 Quick Test Command

For a quick test of the full flow:

```bash
# Terminal 1: Start agent
source venv/bin/activate && python agent.py dev

# Terminal 2: Dispatch call
source venv/bin/activate && python dispatch_calls.py
```

Then answer the phone and test the appointment scheduling!


