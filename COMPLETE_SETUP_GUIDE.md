# Complete Setup Guide: Google Sheets → Calls → Calendar Integration

## ✅ What's Already Working

1. **Google Sheets Reading** - Script reads pending rows ✅
2. **Multiple Numbers** - Calls them one by one with delay ✅
3. **LiveKit Integration** - Dispatches calls to agent ✅
4. **Agent Scheduling** - Agent can schedule appointments via Make.com ✅
5. **Call Results** - Agent sends results back to Make.com ✅

## 📋 Current Workflow

```
Google Sheets (Pending rows)
    ↓
dispatch_calls.py (reads rows, dispatches one by one)
    ↓
LiveKit Cloud (routes to agent)
    ↓
Agent (makes call, schedules appointments)
    ↓
Make.com Webhooks (updates Google Sheets, creates calendar events)
```

## 🔧 What You Need to Set Up

### 1. Make.com Workflow: Schedule Appointments

**Purpose**: When agent schedules an appointment, create Google Calendar event

**Trigger**: Webhook (receives from agent)
- **Webhook URL**: Set this as `MAKE_COM_WEBHOOK_URL` in `.env.local`

**Steps**:
1. **Webhook Trigger** - Receives appointment data
2. **Create Google Calendar Event** - With Google Meet link
3. **Send Email** - Send confirmation email to customer
4. **Update Google Sheets** - Mark appointment scheduled

**Data Received from Agent**:
```json
{
  "email": "customer@example.com",
  "name": "John Doe",
  "phone": "+12095539289",
  "appointment_time": "2025-01-01T14:00:00",
  "appointment_time_display": "2:00 PM on Wednesday, January 1, 2025",
  "summary": "Appointment with John Doe",
  "row_id": "2"
}
```

### 2. Make.com Workflow: Update Call Results

**Purpose**: When call ends, update Google Sheets with results

**Trigger**: Webhook (receives from agent)
- **Webhook URL**: Set this as `MAKE_COM_CALL_RESULTS_WEBHOOK_URL` in `.env.local`

**Steps**:
1. **Webhook Trigger** - Receives call results
2. **Find Google Sheets Row** - By `row_id` or `phone_number`
3. **Update Google Sheets** - With transcript, status, duration, appointment info

**Data Received from Agent**:
```json
{
  "phone_number": "+12095539289",
  "name": "John Doe",
  "call_status": "completed",
  "call_duration_seconds": 120,
  "transcript": "Full conversation transcript...",
  "appointment_scheduled": true,
  "appointment_time": "2025-01-01T14:00:00",
  "appointment_email": "customer@example.com",
  "row_id": "2"
}
```

## 📞 How Multiple Numbers Work

### Current Implementation

The `dispatch_calls.py` script already handles multiple numbers:

1. **Reads all pending rows** from Google Sheets
2. **Processes one at a time** (not in parallel)
3. **Waits between calls** (configurable delay)
4. **Updates status** after each call

### Example Flow

```
Row 1: +12095539289 (Status: Pending)
  → Dispatch call
  → Wait 5 seconds
  → Update Status to "Dispatched"

Row 2: +1987654321 (Status: Pending)
  → Dispatch call
  → Wait 5 seconds
  → Update Status to "Dispatched"

Row 3: +1555123456 (Status: Pending)
  → Dispatch call
  → Wait 5 seconds
  → Update Status to "Dispatched"
```

### Configuration

In `.env.local`:
```bash
CALL_DELAY_SECONDS=5  # Wait 5 seconds between calls
```

### Google Sheet Structure

Your sheet should have:

| Phone_number | Name | Status | Appointment_time | Transcript | Call Duration | Last Called | Row_id |
|--------------|------|--------|------------------|------------|---------------|------------|--------|
| +12095539289 | John | Pending | | | | | |
| +1987654321  | Jane | Pending | | | | | |
| +1555123456  | Bob  | Pending | | | | | |

**To call multiple numbers:**
1. Add rows with `Status = "Pending"`
2. Run `python dispatch_calls.py`
3. Script processes them one by one automatically

## 🎯 Complete Setup Steps

### Step 1: Set Up Make.com Workflows

#### Workflow 1: Schedule Appointments

1. Create new workflow in Make.com
2. Add **Webhook** trigger
3. Copy webhook URL
4. Add to `.env.local`:
   ```bash
   MAKE_COM_WEBHOOK_URL=https://hook.us1.make.com/your-webhook-url
   ```
5. Add **Google Calendar** module → Create Event
6. Add **Email** module → Send confirmation
7. Add **Google Sheets** module → Update row

#### Workflow 2: Update Call Results

1. Create new workflow in Make.com
2. Add **Webhook** trigger
3. Copy webhook URL
4. Add to `.env.local`:
   ```bash
   MAKE_COM_CALL_RESULTS_WEBHOOK_URL=https://hook.us1.make.com/your-results-webhook-url
   ```
5. Add **Google Sheets** module → Update row with:
   - Status
   - Transcript
   - Call Duration
   - Appointment info

### Step 2: Configure Environment Variables

In `.env.local`, add:

```bash
# LiveKit (already set)
LIVEKIT_URL=wss://cold-caller-6vmkvmbr.livekit.cloud
LIVEKIT_API_KEY=APIkzg3gFyEDWWG
LIVEKIT_API_SECRET=1CuQUimQvp8JJO3vv6fsZ3BetuaKxkVWZMUwPyNgQg8
SIP_OUTBOUND_TRUNK_ID=ST_jXCZwUp859wY

# Make.com Webhooks (ADD THESE)
MAKE_COM_WEBHOOK_URL=https://hook.us1.make.com/your-appointment-webhook
MAKE_COM_CALL_RESULTS_WEBHOOK_URL=https://hook.us1.make.com/your-results-webhook

# API Keys (already set)
OPENAI_API_KEY=your_key
DEEPGRAM_API_KEY=your_key
CARTESIA_API_KEY=your_key
GROQ_API_KEY=your_key

# Call Settings
CALL_DELAY_SECONDS=5
```

### Step 3: Test the Complete Flow

1. **Add test row to Google Sheet**:
   - Phone_number: `+12095539289`
   - Name: `Test User`
   - Status: `Pending`

2. **Run dispatch script**:
   ```bash
   python dispatch_calls.py
   ```

3. **Agent makes call**:
   - Agent calls the number
   - During call, if customer wants appointment, agent schedules it
   - Agent sends results to Make.com

4. **Make.com workflows**:
   - Creates Google Calendar event (if appointment scheduled)
   - Sends email to customer
   - Updates Google Sheets with results

5. **Check Google Sheet**:
   - Status updated to "Completed"
   - Transcript added
   - Appointment info added (if scheduled)

## 🔄 Complete Workflow Diagram

```
┌─────────────────┐
│  Google Sheets  │
│  (Pending rows) │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ dispatch_calls  │  ← Reads rows, dispatches one by one
│      .py        │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  LiveKit Cloud  │  ← Routes to agent
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  Agent (Local   │  ← Makes phone call
│   or Cloud)     │
└────────┬─────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌─────────────────┐  ┌─────────────────┐
│ Make.com:       │  │ Make.com:       │
│ Schedule        │  │ Call Results    │
│ Appointment     │  │ Update          │
└────────┬─────────┘  └────────┬─────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐  ┌─────────────────┐
│ Google Calendar │  │  Google Sheets  │
│ (Create Event)  │  │  (Update Row)   │
└─────────────────┘  └─────────────────┘
```

## 📝 Next Steps

1. ✅ **Set up Make.com workflows** (see above)
2. ✅ **Add webhook URLs to `.env.local`**
3. ✅ **Test with one number**
4. ✅ **Add multiple numbers to Google Sheet**
5. ✅ **Run dispatch script**
6. ✅ **Monitor results in Google Sheets**

## 🎉 You're Done!

Once Make.com workflows are set up, the complete system will:
- ✅ Read numbers from Google Sheets
- ✅ Call them one by one
- ✅ Schedule appointments during calls
- ✅ Create Google Calendar events
- ✅ Send confirmation emails
- ✅ Update Google Sheets with results

Everything else is already working! 🚀


