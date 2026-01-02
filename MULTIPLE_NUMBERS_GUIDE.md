# How Multiple Numbers Are Handled

## ✅ It Already Works!

The script **automatically processes multiple numbers** from your Google Sheet. Here's exactly how:

## 📋 How It Works

### Step 1: Reads ALL Pending Rows

The script reads your entire Google Sheet and finds **ALL rows** where:
- `Status = "Pending"` (case-insensitive)
- `Phone_number` is not empty

**Example Google Sheet:**
```
| Phone_number   | Name      | Status  |
|----------------|-----------|---------|
| +12095539289   | John      | Pending | ← Will be called
| +1987654321    | Jane      | Pending | ← Will be called
| +1555123456    | Bob       | Pending | ← Will be called
| +1999888777    | Alice     | Completed| ← Skipped (not Pending)
```

### Step 2: Processes One at a Time

The script processes them **sequentially** (one after another), not in parallel:

```
Call 1: +12095539289 (John)
  → Dispatch call
  → Update Status to "Dispatched"
  → Wait 5 seconds

Call 2: +1987654321 (Jane)
  → Dispatch call
  → Update Status to "Dispatched"
  → Wait 5 seconds

Call 3: +1555123456 (Bob)
  → Dispatch call
  → Update Status to "Dispatched"
  → Done!
```

### Step 3: Configurable Delay

Between each call, the script waits (default: 5 seconds). This prevents:
- Overwhelming the agent
- Rate limiting issues
- Too many simultaneous calls

**Configure delay in `.env.local`:**
```bash
CALL_DELAY_SECONDS=5  # Wait 5 seconds between calls
```

Change to `10` for 10 seconds, `30` for 30 seconds, etc.

## 📊 Example Output

When you run `python dispatch_calls.py` with 3 pending rows:

```
============================================================
LiveKit Call Dispatcher
============================================================
✓ Google Sheets authentication successful
Reading pending rows from sheet: 1hpr2PnycZIhXSBuzKFTyiLBpivgP5oq3sD1bf3vwcQU
Found 3 pending rows
Starting to process 3 calls...

[1/3] Processing call to +12095539289 (Row 2)...
✓ Call dispatched successfully. Job ID: created
Waiting 5 seconds before next call...

[2/3] Processing call to +1987654321 (Row 3)...
✓ Call dispatched successfully. Job ID: created
Waiting 5 seconds before next call...

[3/3] Processing call to +1555123456 (Row 4)...
✓ Call dispatched successfully. Job ID: created

=== Summary ===
Total calls: 3
Successful: 3
Failed: 0
============================================================
```

## 🎯 How to Use Multiple Numbers

### Option 1: Add All at Once

1. Add multiple rows to Google Sheet:
   ```
   Row 2: +12095539289 | John | Pending
   Row 3: +1987654321  | Jane | Pending
   Row 4: +1555123456  | Bob  | Pending
   ```

2. Run dispatch script **once**:
   ```bash
   python dispatch_calls.py
   ```

3. Script processes **all of them** automatically!

### Option 2: Add Incrementally

1. Add one row: `+12095539289 | John | Pending`
2. Run: `python dispatch_calls.py` → Calls John
3. Add another row: `+1987654321 | Jane | Pending`
4. Run: `python dispatch_calls.py` → Calls Jane
5. Repeat as needed

## ⚙️ Configuration

### Delay Between Calls

In `.env.local`:
```bash
# Wait 5 seconds between calls (default)
CALL_DELAY_SECONDS=5

# Wait 10 seconds (more conservative)
CALL_DELAY_SECONDS=10

# Wait 30 seconds (very conservative)
CALL_DELAY_SECONDS=30
```

### Maximum Calls Per Run

The script reads up to 1000 rows (configurable in code). To change:

In `dispatch_calls.py`, line 120:
```python
range_name = f"{SHEET_NAME}!A1:Z1000"  # Change 1000 to your limit
```

## 🔄 What Happens During Processing

For each number:

1. **Read from Sheet** → Gets phone number, name, etc.
2. **Update Status** → Changes "Pending" to "Dispatched"
3. **Dispatch Call** → Sends job to LiveKit
4. **Wait** → Pauses before next call (prevents overload)
5. **Repeat** → Moves to next number

## 📝 Google Sheet Status Updates

As calls are processed, your sheet updates in real-time:

**Before:**
```
| Phone_number   | Name | Status  |
|----------------|------|---------|
| +12095539289   | John | Pending |
| +1987654321    | Jane | Pending |
| +1555123456    | Bob  | Pending |
```

**After (during processing):**
```
| Phone_number   | Name | Status    | Last Called        |
|----------------|------|-----------|---------------------|
| +12095539289   | John | Dispatched | 2025-12-31 10:00:00 |
| +1987654321    | Jane | Dispatched | 2025-12-31 10:00:05 |
| +1555123456    | Bob  | Dispatched | 2025-12-31 10:00:10 |
```

**After calls complete** (agent updates via `update_call_results.py`):
```
| Phone_number   | Name | Status    | Transcript | Call Duration |
|----------------|------|-----------|------------|---------------|
| +12095539289   | John | Completed | "..."      | 120 seconds    |
| +1987654321    | Jane | Completed | "..."      | 90 seconds    |
| +1555123456    | Bob  | Voicemail | ""         | 5 seconds     |
```

## 🚀 Best Practices

### 1. Batch Processing

Add all numbers you want to call, then run script once:
- ✅ More efficient
- ✅ Better tracking
- ✅ Single summary report

### 2. Reasonable Delays

Don't set delay too low:
- ❌ `CALL_DELAY_SECONDS=1` → Might overwhelm agent
- ✅ `CALL_DELAY_SECONDS=5` → Good balance
- ✅ `CALL_DELAY_SECONDS=10` → Very safe

### 3. Monitor Progress

Watch the terminal output to see:
- Which number is being called
- Success/failure status
- Final summary

## 🎯 Summary

**The script already handles multiple numbers!**

- ✅ Reads ALL pending rows automatically
- ✅ Processes them one by one
- ✅ Waits between calls (configurable)
- ✅ Updates status for each
- ✅ Shows progress and summary

**Just add multiple rows with `Status = "Pending"` and run the script once!** 🚀


