# Retry System for "No Answer" Calls

## Overview

The dispatch script now automatically retries calls that resulted in "No Answer" status. On each run, it will:
1. Call all rows with `Status = "Pending"` (first attempt)
2. Also call all rows with `Status = "No Answer"` that haven't exceeded the max retry limit

## How It Works

### First Run
- Script finds all rows with `Status = "Pending"`
- Calls each one
- If call results in "No Answer", the agent sets status to "No Answer"

### Subsequent Runs
- Script finds:
  - All rows with `Status = "Pending"` (new calls)
  - All rows with `Status = "No Answer"` that have retry count < MAX_RETRIES
- Calls both groups
- Increments retry count for "No Answer" retries

### Retry Limit
- Default: 3 retries (configurable via `MAX_RETRIES` env var)
- After max retries, those rows are skipped
- You can manually reset retry count or status to retry again

## Configuration

Add these to your `.env.local`:

```bash
# Enable/disable retry for "No Answer" calls (default: true)
RETRY_NO_ANSWER=true

# Maximum number of retry attempts (default: 3)
MAX_RETRIES=3
```

## Google Sheet Setup

### Required Column
Add a **"Retry Count"** column to your Google Sheet (optional but recommended):
- If column exists: Tracks retry attempts per row
- If column doesn't exist: Will still retry, but won't track count

### Status Flow
```
Pending → Dispatched → No Answer → (Retry) → Dispatched → No Answer → ...
```

After MAX_RETRIES, the row will be skipped on future runs.

## Example

**Row 1:**
- First run: Status = "Pending" → Call → "No Answer" → Retry Count = 0
- Second run: Status = "No Answer", Retry Count = 0 → Call → "No Answer" → Retry Count = 1
- Third run: Status = "No Answer", Retry Count = 1 → Call → "No Answer" → Retry Count = 2
- Fourth run: Status = "No Answer", Retry Count = 2 → Call → "No Answer" → Retry Count = 3
- Fifth run: Status = "No Answer", Retry Count = 3 → **SKIPPED** (exceeded MAX_RETRIES)

## Logging

The script will log:
- `Found X rows to call: Y new (Pending) + Z retries (No Answer)`
- `Row N: Found 'No Answer' with retry count X/3 - will retry`
- `Row N: 'No Answer' but exceeded max retries (3/3) - skipping`

## Manual Reset

To manually retry a row that exceeded max retries:
1. Set `Status` back to "Pending" or "No Answer"
2. Set `Retry Count` to 0 (or delete the value)
3. Run the script again

## Disable Retries

To disable automatic retries:
```bash
RETRY_NO_ANSWER=false
```

This will only call rows with `Status = "Pending"` and ignore "No Answer" rows.

