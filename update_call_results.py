#!/usr/bin/env python3
"""
Update Google Sheets with call results.

This script can be used as a webhook receiver to update Google Sheets
with call results from the LiveKit agent.
"""

import os
import json
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional
from datetime import datetime

# Google Sheets API
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv(dotenv_path=".env.local")

# Configuration
GOOGLE_SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1hpr2PnycZIhXSBuzKFTyiLBpivgP5oq3sD1bf3vwcQU")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("update-call-results")


def get_google_sheets_service():
    """Authenticate and return Google Sheets service."""
    creds = None
    
    token_file = "google_sheets_token.json"
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, GOOGLE_SHEETS_SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise FileNotFoundError(
                "Google Sheets not authenticated. Run dispatch_calls.py first to authenticate."
            )
    
    return build("sheets", "v4", credentials=creds)


def get_column_index(headers: list, column_name: str) -> Optional[int]:
    """Get the index of a column by name."""
    try:
        return headers.index(column_name)
    except ValueError:
        for i, header in enumerate(headers):
            if header.lower() == column_name.lower():
                return i
        return None


def update_call_results(service, call_data: Dict[str, Any]):
    """Update Google Sheets with call results."""
    try:
        # Get headers
        range_name = f"{SHEET_NAME}!A1:Z1"
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name
        ).execute()
        
        headers = result.get("values", [])[0] if result.get("values") else []
        
        # Find row by row_id or phone_number
        row_number = None
        if call_data.get("row_id"):
            try:
                row_number = int(call_data["row_id"])
            except (ValueError, TypeError):
                pass
        
        # If no row_id, search by phone number
        if not row_number:
            phone_number = call_data.get("phone_number", "")
            if phone_number:
                # Read all rows to find matching phone number
                range_name = f"{SHEET_NAME}!A2:Z1000"
                result = service.spreadsheets().values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=range_name
                ).execute()
                
                values = result.get("values", [])
                phone_idx = get_column_index(headers, "Phone Number")
                
                if phone_idx is not None:
                    for i, row in enumerate(values, start=2):
                        if len(row) > phone_idx and row[phone_idx].strip() == phone_number:
                            row_number = i
                            break
        
        if not row_number:
            logger.warning(f"Could not find row for phone number: {call_data.get('phone_number')}")
            return False
        
        # Prepare updates
        updates = {}
        
        # Map call status
        call_status = call_data.get("call_status", "unknown")
        status_map = {
            "completed": "Completed",
            "voicemail": "Voicemail",
            "failed": "Failed",
            "no_answer": "No Answer"
        }
        updates["Status"] = status_map.get(call_status.lower(), call_status.capitalize())
        
        # Update transcript if column exists
        if "Transcript" in headers and call_data.get("transcript"):
            updates["Transcript"] = call_data["transcript"]
        
        # Update appointment info
        if call_data.get("appointment_scheduled"):
            if "Appointment Scheduled" in headers:
                updates["Appointment Scheduled"] = "Yes"
            if "Appointment Time Scheduled" in headers and call_data.get("appointment_time"):
                updates["Appointment Time Scheduled"] = call_data["appointment_time"]
            if "Appointment Email" in headers and call_data.get("appointment_email"):
                updates["Appointment Email"] = call_data["appointment_email"]
        
        # Update call duration
        if "Call Duration" in headers and call_data.get("call_duration_seconds"):
            duration = call_data["call_duration_seconds"]
            updates["Call Duration"] = f"{duration} seconds"
        
        # Update last called timestamp
        if "Last Called" in headers:
            updates["Last Called"] = call_data.get("timestamp", datetime.now().isoformat())
        
        # Batch update
        if updates:
            update_data = []
            for column_name, value in updates.items():
                col_idx = get_column_index(headers, column_name)
                if col_idx is not None:
                    if col_idx < 26:
                        col_letter = chr(65 + col_idx)
                    else:
                        col_letter = chr(64 + (col_idx // 26)) + chr(65 + (col_idx % 26))
                    
                    range_to_update = f"{SHEET_NAME}!{col_letter}{row_number}"
                    update_data.append({
                        "range": range_to_update,
                        "values": [[str(value)]]
                    })
            
            if update_data:
                body = {
                    "valueInputOption": "RAW",
                    "data": update_data
                }
                
                service.spreadsheets().values().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body=body
                ).execute()
                
                logger.info(f"Updated row {row_number} with call results: {', '.join(updates.keys())}")
                return True
        
        return False
    
    except Exception as e:
        logger.error(f"Error updating call results: {e}")
        return False


def update_from_webhook_data(webhook_data: Dict[str, Any]):
    """Update Google Sheets from webhook data (for use as webhook receiver)."""
    try:
        service = get_google_sheets_service()
        return update_call_results(service, webhook_data)
    except Exception as e:
        logger.error(f"Failed to update from webhook: {e}")
        return False


def main():
    """Main function - can be used to test with sample data."""
    import sys
    
    if len(sys.argv) > 1:
        # Read JSON from file or stdin
        if sys.argv[1] == "-":
            data = json.load(sys.stdin)
        else:
            with open(sys.argv[1], "r") as f:
                data = json.load(f)
        
        update_from_webhook_data(data)
    else:
        print("Usage: update_call_results.py <json_file>")
        print("Or pipe JSON: echo '{\"phone_number\":\"+1234567890\",\"call_status\":\"completed\"}' | python update_call_results.py -")


if __name__ == "__main__":
    main()





