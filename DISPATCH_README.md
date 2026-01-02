# Google Sheets to LiveKit Call Dispatcher

This Python script reads phone numbers from Google Sheets and dispatches calls to LiveKit one at a time, then updates the sheet with call status.

## Features

- ✅ Reads pending calls from Google Sheets
- ✅ Dispatches calls one at a time (with configurable delay)
- ✅ Updates Google Sheets with dispatch status
- ✅ Handles authentication automatically
- ✅ Uses LiveKit Python SDK (no JWT issues!)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Google Sheets API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Google Sheets API**:
   - Go to "APIs & Services" → "Library"
   - Search for "Google Sheets API"
   - Click "Enable"
4. Create OAuth 2.0 Credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Application type: **Desktop app**
   - Name it (e.g., "Call Dispatcher")
   - Click "Create"
   - Click "Download JSON"
   - Save the file as `credentials.json` in your project root

### 3. Configure Environment Variables

Make sure your `.env.local` has:

```bash
# LiveKit Configuration
LIVEKIT_URL=https://cold-caller-6vmkvmbr.livekit.cloud
LIVEKIT_API_KEY=APIkzg3gFyEDWWG
LIVEKIT_API_SECRET=1CuQUimQvp8JJO3vv6fsZ3BetuaKxkVWZMUwPyNgQg8

# Google Sheets Configuration (optional - defaults provided)
GOOGLE_SHEET_ID=1hpr2PnycZIhXSBuzKFTyiLBpivgP5oq3sD1bf3vwcQU
GOOGLE_SHEET_NAME=Sheet1

# Call Settings (optional)
CALL_DELAY_SECONDS=5  # Delay between calls in seconds
```

### 4. Prepare Your Google Sheet

Your Google Sheet should have these columns:

| Phone Number | Name | Status | Appointment Time | Transcript | Call Duration | Last Called | ... |
|--------------|------|--------|------------------|------------|---------------|-------------|-----|
| +12095539289 | John | Pending | | | | | |
| +1987654321  | Jane | Pending | Tomorrow 2pm | | | | |

**Required columns:**
- `Phone Number` - Must have + prefix (e.g., +12095539289)
- `Status` - Set to "Pending" for rows to call

**Optional columns (will be updated automatically):**
- `Transcript` - Full conversation transcript
- `Call Duration` - Duration in seconds
- `Last Called` - Timestamp of call
- `Appointment Scheduled` - Yes/No
- `Appointment Time Scheduled` - ISO timestamp
- `Appointment Email` - Email used for calendar invite

## Usage

### Basic Usage

```bash
python dispatch_calls.py
```

The script will:
1. Authenticate with Google Sheets (first time opens browser)
2. Read all rows with Status = "Pending"
3. Dispatch calls one at a time
4. Update Status to "Dispatched" for each call
5. Wait 5 seconds between calls (configurable)

### First Run

On first run, it will:
1. Open your browser for Google authentication
2. Ask you to sign in and authorize
3. Save credentials to `google_sheets_token.json` for future runs

### Example Output

```
2025-12-30 12:00:00 - dispatch-calls - INFO - Starting call dispatch process...
2025-12-30 12:00:01 - dispatch-calls - INFO - Found 3 pending rows
2025-12-30 12:00:01 - dispatch-calls - INFO - [1/3] Processing call to +12095539289 (Row 2)...
2025-12-30 12:00:02 - dispatch-calls - INFO - ✓ Call dispatched successfully. Job ID: job_abc123
2025-12-30 12:00:07 - dispatch-calls - INFO - [2/3] Processing call to +1987654321 (Row 3)...
...
```

## How Call Results Are Updated

The agent automatically sends call results to Make.com webhook (configured in `agent.py`). 

To update Google Sheets directly with call results, you have two options:

### Option 1: Use Make.com Webhook (Current Setup)

Your agent already sends results to `MAKE_COM_CALL_RESULTS_WEBHOOK_URL`. Set up a Make.com workflow to:
1. Receive webhook with call results
2. Update Google Sheets row with transcript, status, etc.

### Option 2: Direct Google Sheets Update (Alternative)

You can modify `agent.py` to also update Google Sheets directly by calling the `update_call_results.py` script, or set up a local webhook server.

## Scheduling

### Run on Schedule (Linux/Mac)

Add to crontab to run every hour:

```bash
crontab -e
```

Add:
```
0 * * * * cd /path/to/outboundcaller-1 && /path/to/venv/bin/python dispatch_calls.py >> /path/to/logs/dispatch.log 2>&1
```

### Run on Schedule (Windows)

Use Task Scheduler to run the script periodically.

## Troubleshooting

### "credentials.json not found"
- Download OAuth 2.0 credentials from Google Cloud Console
- Save as `credentials.json` in project root

### "No pending calls to dispatch"
- Check your Google Sheet has rows with Status = "Pending"
- Verify column names match exactly (case-sensitive)

### "Failed to dispatch to LiveKit"
- Check `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` in `.env.local`
- Verify agent worker is running: `python agent.py dev`
- Check agent name matches: `outbound-caller-dev`

### "Missing required columns"
- Ensure your sheet has "Status" and "Phone Number" columns
- Column names are case-sensitive

## Advanced Configuration

### Custom Column Names

If your sheet uses different column names, modify the `get_column_index()` function calls in `dispatch_calls.py` to match your column names.

### Call Delay

Adjust delay between calls:
```bash
# In .env.local
CALL_DELAY_SECONDS=10  # Wait 10 seconds between calls
```

## Files

- `dispatch_calls.py` - Main script to dispatch calls
- `update_call_results.py` - Script to update Google Sheets with call results
- `credentials.json` - Google OAuth credentials (download from Google Cloud)
- `google_sheets_token.json` - Saved authentication token (auto-generated)

## Next Steps

1. Run `python dispatch_calls.py` to start dispatching calls
2. Monitor your Google Sheet - Status will update to "Dispatched"
3. Check your agent logs to see calls being made
4. Call results will be sent to Make.com webhook (if configured)


