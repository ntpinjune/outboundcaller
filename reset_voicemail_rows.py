#!/usr/bin/env python3
"""
Reset Voicemail Rows Script

Finds rows in Google Sheets where Status is "voicemail", clears the data 
(except Phone_number and Business name), and sets Status to "Pending".
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env.local", override=True)

from dispatch_calls import get_google_sheets_service, SPREADSHEET_ID, SHEET_NAME

# Column headers and their indices (0-based)
HEADERS = [
    "Phone_number",      # 0 - Keep
    "Name",              # 1 - Clear
    "Status",            # 2 - Set to "Pending"
    "Appointment Scheduled",  # 3 - Clear
    "Appointment Time Scheduled",  # 4 - Clear
    "Appointment Email",  # 5 - Clear
    "Transcript",        # 6 - Clear
    "Call Duration",     # 7 - Clear
    "Last Called",       # 8 - Clear
    "Business name",     # 9 - Keep
    "Room Name",         # 10 - Clear
    "Session ID",        # 11 - Clear
    "Outcome Details",   # 12 - Clear
]

# Columns to KEEP (0-indexed)
KEEP_COLUMNS = {0, 9}  # Phone_number, Business name

# Status column index
STATUS_COL = 2


def get_column_letter(col_idx: int) -> str:
    """Convert 0-based column index to Excel-style column letter."""
    if col_idx < 26:
        return chr(65 + col_idx)
    else:
        return chr(64 + (col_idx // 26)) + chr(65 + (col_idx % 26))


def reset_voicemail_rows():
    """Find voicemail rows and reset them to pending."""
    print("=" * 60)
    print("Reset Voicemail Rows Script")
    print("=" * 60)
    
    # Get Google Sheets service
    print("\n[1/4] Connecting to Google Sheets...")
    service = get_google_sheets_service()
    
    # Read all data from sheet
    print(f"[2/4] Reading data from sheet: {SHEET_NAME}")
    range_name = f"{SHEET_NAME}!A:M"  # Columns A through M (13 columns)
    
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
    ).execute()
    
    values = result.get("values", [])
    
    if not values:
        print("No data found in sheet!")
        return
    
    # First row is headers
    headers = values[0]
    print(f"   Found {len(values) - 1} data rows")
    print(f"   Headers: {headers}")
    
    # Find Status column index
    try:
        status_idx = headers.index("Status")
    except ValueError:
        print("ERROR: 'Status' column not found in headers!")
        return
    
    # Find voicemail rows
    print("\n[3/4] Finding voicemail rows...")
    voicemail_rows = []
    
    for row_num, row in enumerate(values[1:], start=2):  # Start from row 2 (1-indexed)
        # Get status value (handle rows with fewer columns)
        if len(row) > status_idx:
            status = row[status_idx].strip().lower()
            if status == "voicemail":
                phone = row[0] if len(row) > 0 else ""
                business = row[9] if len(row) > 9 else ""
                voicemail_rows.append({
                    "row_num": row_num,
                    "phone": phone,
                    "business": business,
                })
    
    if not voicemail_rows:
        print("   No voicemail rows found!")
        return
    
    print(f"   Found {len(voicemail_rows)} voicemail rows:")
    for row_info in voicemail_rows[:10]:  # Show first 10
        print(f"      Row {row_info['row_num']}: {row_info['phone']} - {row_info['business']}")
    if len(voicemail_rows) > 10:
        print(f"      ... and {len(voicemail_rows) - 10} more")
    
    # Confirm with user
    confirm = input(f"\nReset {len(voicemail_rows)} voicemail rows to Pending? (y/n): ")
    if confirm.lower() != "y":
        print("Cancelled.")
        return
    
    # Reset each voicemail row
    print("\n[4/4] Resetting rows...")
    batch_data = []
    
    for row_info in voicemail_rows:
        row_num = row_info["row_num"]
        phone = row_info["phone"]
        business = row_info["business"]
        
        # Build the new row: keep Phone_number and Business name, clear rest, set Status to Pending
        new_row = []
        for col_idx in range(len(HEADERS)):
            if col_idx == 0:  # Phone_number - keep
                new_row.append(phone)
            elif col_idx == 9:  # Business name - keep
                new_row.append(business)
            elif col_idx == 2:  # Status - set to Pending
                new_row.append("Pending")
            else:
                new_row.append("")  # Clear
        
        # Add to batch update
        range_to_update = f"{SHEET_NAME}!A{row_num}:M{row_num}"
        batch_data.append({
            "range": range_to_update,
            "values": [new_row]
        })
    
    # Execute batch update
    body = {
        "valueInputOption": "RAW",
        "data": batch_data
    }
    
    result = service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body=body
    ).execute()
    
    print(f"\n[OK] Successfully reset {len(voicemail_rows)} rows!")
    print(f"     Total cells updated: {result.get('totalUpdatedCells', 0)}")
    print("\nDone!")


if __name__ == "__main__":
    reset_voicemail_rows()
