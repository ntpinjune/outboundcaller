#!/usr/bin/env python3
"""
Dispatch outbound calls from Google Sheets to LiveKit.

This script:
1. Reads pending rows from Google Sheets
2. Dispatches calls to LiveKit one at a time
3. Updates Google Sheets with call status and results
"""

import os
import json
import logging
import time
import base64
import hmac
import hashlib
import subprocess
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from datetime import datetime

# Google Sheets API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# HTTP requests
import requests

# Load environment variables
load_dotenv(dotenv_path=".env.local")

# Configuration
GOOGLE_SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1hpr2PnycZIhXSBuzKFTyiLBpivgP5oq3sD1bf3vwcQU")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")
AGENT_NAME = "outbound-caller-dev"

# LiveKit credentials
# Ensure URL uses https:// (not wss://) for HTTP requests
# For local agent: Make sure you're running `python agent.py dev` locally
# The dispatch will go through LiveKit Cloud but will route to your local agent if it's running
livekit_url_raw = os.getenv("LIVEKIT_URL", "https://cold-caller-6vmkvmbr.livekit.cloud")
LIVEKIT_URL = livekit_url_raw.replace("wss://", "https://").replace("ws://", "http://")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# Use local agent if specified (set USE_LOCAL_AGENT=true in .env.local)
# When using local agent, make sure cloud agent is stopped to avoid conflicts
USE_LOCAL_AGENT = os.getenv("USE_LOCAL_AGENT", "false").lower() == "true"

# Call settings
CALL_DELAY_SECONDS = int(os.getenv("CALL_DELAY_SECONDS", "5"))  # Delay between calls
MAX_CALL_DURATION = int(os.getenv("MAX_CALL_DURATION", "300"))  # Max call duration in seconds
WAIT_FOR_CALL_COMPLETION = os.getenv("WAIT_FOR_CALL_COMPLETION", "true").lower() == "true"  # Wait for each call to finish before next
CALL_COMPLETION_CHECK_INTERVAL = int(os.getenv("CALL_COMPLETION_CHECK_INTERVAL", "10"))  # Check every 10 seconds if call is done
MAX_WAIT_TIME = int(os.getenv("MAX_WAIT_TIME", "600"))  # Max 10 minutes per call
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))  # Maximum number of retry attempts for "No Answer" calls
RETRY_NO_ANSWER = os.getenv("RETRY_NO_ANSWER", "true").lower() == "true"  # Whether to retry "No Answer" calls on next run

logging.basicConfig(
    level=logging.INFO,  # INFO level - shows important messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dispatch-calls")


def get_google_sheets_service():
    """Authenticate and return Google Sheets service."""
    creds = None
    
    # Check for existing token
    token_file = "google_sheets_token.json"
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, GOOGLE_SHEETS_SCOPES)
    
    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials_file = "credentials.json"
            if not os.path.exists(credentials_file):
                raise FileNotFoundError(
                    f"{credentials_file} not found. Download from Google Cloud Console:\n"
                    "1. Go to: https://console.cloud.google.com/apis/credentials\n"
                    "2. Create OAuth 2.0 Client ID (Desktop app)\n"
                    "3. Download and save as credentials.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, GOOGLE_SHEETS_SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open(token_file, "w") as token:
            token.write(creds.to_json())
        logger.info("Google Sheets authentication successful")
    
    return build("sheets", "v4", credentials=creds)


def get_column_index(headers: List[str], column_name: str) -> Optional[int]:
    """Get the index of a column by name."""
    try:
        return headers.index(column_name)
    except ValueError:
        # Try case-insensitive search
        for i, header in enumerate(headers):
            # Normalize both: strip whitespace and compare lowercase
            header_normalized = header.strip().lower()
            column_normalized = column_name.strip().lower()
            if header_normalized == column_normalized:
                return i
        return None


def read_pending_rows(service) -> List[Dict[str, Any]]:
    """Read rows from Google Sheets with Status = 'Pending' or 'No Answer' (for retries).
    
    If RETRY_NO_ANSWER is enabled, will also include rows with "No Answer" status
    that haven't exceeded MAX_RETRIES.
    """
    try:
        # Read all rows
        range_name = f"{SHEET_NAME}!A1:Z1000"
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name
        ).execute()
        
        values = result.get("values", [])
        
        if not values:
            logger.info("No data found in sheet")
            return []
        
        # First row is headers
        headers = values[0]
        
        # Find column indices (try multiple variations)
        status_idx = get_column_index(headers, "Status")
        # Try different phone column name variations (check for None explicitly, not falsy 0)
        phone_idx = get_column_index(headers, "Phone_number")
        if phone_idx is None:
            phone_idx = get_column_index(headers, "Phone Number")
        if phone_idx is None:
            phone_idx = get_column_index(headers, "PhoneNumber")
        
        name_idx = get_column_index(headers, "Name")
        
        # Try different appointment column name variations
        appointment_idx = get_column_index(headers, "Appointment_time")
        if appointment_idx is None:
            appointment_idx = get_column_index(headers, "Appointment Time")
        if appointment_idx is None:
            appointment_idx = get_column_index(headers, "AppointmentTime")
        
        # Find Retry Count column (optional)
        retry_count_idx = get_column_index(headers, "Retry Count")
        
        if status_idx is None or phone_idx is None:
            logger.error(f"Missing required columns. Found: {headers}")
            logger.error(f"Status index: {status_idx}, Phone index: {phone_idx}")
            logger.error(f"Looking for 'Status' and 'Phone Number' (or 'Phone_number' or 'PhoneNumber')")
            return []
        
        # Filter for pending rows and "No Answer" rows (if retry enabled)
        pending_rows = []
        for i, row in enumerate(values[1:], start=2):  # Start from row 2 (skip header)
            # Pad row to match header length
            while len(row) < len(headers):
                row.append("")
            
            status = row[status_idx].strip().lower() if len(row) > status_idx else ""
            phone_number = row[phone_idx].strip() if len(row) > phone_idx else ""
            
            # Skip if no phone number
            if not phone_number:
                continue
            
            # Check if status is "Pending" (first attempt)
            is_pending = status == "pending"
            
            # Check if status is "No Answer" and retry is enabled
            is_no_answer_retry = False
            if RETRY_NO_ANSWER and status == "no answer":
                # Check retry count if column exists
                if retry_count_idx is not None and len(row) > retry_count_idx:
                    try:
                        retry_count = int(row[retry_count_idx].strip() or "0")
                        if retry_count < MAX_RETRIES:
                            is_no_answer_retry = True
                            logger.info(f"Row {i}: Found 'No Answer' with retry count {retry_count}/{MAX_RETRIES} - will retry")
                        else:
                            logger.debug(f"Row {i}: 'No Answer' but exceeded max retries ({retry_count}/{MAX_RETRIES}) - skipping")
                    except (ValueError, TypeError):
                        # If retry count is invalid, treat as 0 and allow retry
                        is_no_answer_retry = True
                        logger.info(f"Row {i}: Found 'No Answer' with invalid retry count - will retry")
                else:
                    # No retry count column, allow retry if enabled
                    is_no_answer_retry = True
                    logger.info(f"Row {i}: Found 'No Answer' (no retry count column) - will retry")
            
            if is_pending or is_no_answer_retry:
                # Ensure phone number exists
                if phone_number:
                    name = row[name_idx].strip() if name_idx and len(row) > name_idx and row[name_idx].strip() else "Customer"
                    appointment_time = row[appointment_idx].strip() if appointment_idx and len(row) > appointment_idx and row[appointment_idx].strip() else ""
                    
                    # Get current retry count
                    current_retry_count = 0
                    if retry_count_idx is not None and len(row) > retry_count_idx:
                        try:
                            current_retry_count = int(row[retry_count_idx].strip() or "0")
                        except (ValueError, TypeError):
                            current_retry_count = 0
                    
                    # Increment retry count if this is a retry
                    if is_no_answer_retry:
                        current_retry_count += 1
                    
                    row_data = {
                        "row_number": i,
                        "phone_number": phone_number,
                        "name": name,
                        "appointment_time": appointment_time,
                        "status": row[status_idx].strip(),
                        "retry_count": current_retry_count,
                        "is_retry": is_no_answer_retry
                    }
                    pending_rows.append(row_data)
        
        pending_count = sum(1 for r in pending_rows if not r.get("is_retry", False))
        retry_count = sum(1 for r in pending_rows if r.get("is_retry", False))
        logger.info(f"Found {len(pending_rows)} rows to call: {pending_count} new (Pending) + {retry_count} retries (No Answer)")
        return pending_rows
    
    except HttpError as error:
        logger.error(f"Error reading Google Sheets: {error}")
        return []


def normalize_phone_number(phone: str) -> str:
    """Ensure phone number has + prefix and no spaces."""
    # Remove all spaces
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Add + if missing
    if not phone.startswith("+"):
        phone = "+" + phone
    
    return phone


def generate_livekit_jwt() -> str:
    """Generate a JWT token for LiveKit API authentication."""
    import time
    
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": LIVEKIT_API_KEY,
        "exp": now + 3600,
        "nbf": now - 10,
        "video": {
            "roomCreate": True,
            "roomJoin": True,
            "roomList": True,
            "roomRecord": True,
            "roomAdmin": True,
            "room": "*"
        }
    }
    
    # Base64 URL encode (JWT format)
    def base64url_encode(data):
        json_str = json.dumps(data, separators=(',', ':'))
        encoded = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')
        return encoded.rstrip('=')
    
    encoded_header = base64url_encode(header)
    encoded_payload = base64url_encode(payload)
    
    # Create signature
    message = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(
        LIVEKIT_API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def dispatch_to_livekit_cli(row_data: Dict[str, Any]) -> Optional[str]:
    """Dispatch a call to LiveKit using CLI (more reliable, matches working CLI command).
    
    Returns:
        Job ID if successful, None otherwise
    """
    try:
        # Normalize phone number
        phone_number = normalize_phone_number(row_data["phone_number"])
        
        # Prepare metadata (same format as CLI command)
        metadata = {
            "phone_number": phone_number,
            "name": row_data["name"],
            "appointment_time": row_data.get("appointment_time", ""),
            "row_id": str(row_data["row_number"])
        }
        
        # Build CLI command (matches: lk dispatch create --new-room --agent-name outbound-caller-dev --metadata '...')
        cmd = [
            "lk", "dispatch", "create",
            "--new-room",
            "--agent-name", AGENT_NAME,
            "--metadata", json.dumps(metadata)
        ]
        
        # Add flag to prefer local agent if specified
        if USE_LOCAL_AGENT:
            logger.info(f"🚀 Dispatching to LOCAL agent (make sure 'python agent.py dev' is running)")
            # The CLI will automatically route to local agent if it's registered
        else:
            logger.info(f"☁️  Dispatching to CLOUD agent")
        
        logger.info(f"Using LiveKit CLI to dispatch call to {phone_number}")
        logger.debug(f"CLI command: {' '.join(cmd)}")
        
        # Run CLI command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Successfully dispatched call to {phone_number} via CLI")
            if result.stdout:
                logger.debug(f"CLI output: {result.stdout}")
            return "created"
        else:
            logger.error(f"❌ CLI dispatch failed with code {result.returncode}")
            logger.error(f"CLI stderr: {result.stderr}")
            logger.error(f"CLI stdout: {result.stdout}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error("❌ CLI command timed out")
        return None
    except FileNotFoundError:
        logger.warning("⚠️  LiveKit CLI not found. Falling back to HTTP API...")
        return dispatch_to_livekit_http(row_data)
    except Exception as e:
        logger.error(f"❌ Error running CLI: {e}")
        logger.warning("⚠️  Falling back to HTTP API...")
        return dispatch_to_livekit_http(row_data)


def dispatch_to_livekit_http(row_data: Dict[str, Any]) -> Optional[str]:
    """Dispatch a call to LiveKit using HTTP API (fallback method).
    
    Returns:
        Job ID if successful, None otherwise
    """
    try:
        # Normalize phone number
        phone_number = normalize_phone_number(row_data["phone_number"])
        
        # Prepare metadata
        metadata = {
            "phone_number": phone_number,
            "name": row_data["name"],
            "appointment_time": row_data.get("appointment_time", ""),
            "row_id": str(row_data["row_number"])
        }
        
        # Generate JWT token
        jwt_token = generate_livekit_jwt()
        
        # Make API request
        url = f"{LIVEKIT_URL}/twirp/livekit.AgentService/CreateJob"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        # Match CLI behavior: --new-room creates a new room
        # When room_name is empty or omitted, LiveKit creates a new room automatically
        # But we'll explicitly set it to empty string to match CLI's --new-room behavior
        payload = {
            "job": {
                "agent_name": AGENT_NAME,
                "room_name": "",  # Empty = create new room (same as --new-room in CLI)
                "metadata": json.dumps(metadata)
            }
        }
        
        logger.info(f"Request URL: {url}")
        logger.info(f"Agent name: {AGENT_NAME}")
        logger.info(f"JWT token length: {len(jwt_token)}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # Log response details for debugging
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response text (first 500 chars): {response.text[:500]}")
        
        # Check for errors
        if response.status_code != 200:
            logger.error(f"❌ LiveKit API returned status {response.status_code}")
            logger.error(f"Full response: {response.text}")
            response.raise_for_status()
            return None
        
        # LiveKit returns "OK" as plain text on success, or JSON with job details
        response_text = response.text.strip()
        
        if response_text == "OK" or response.status_code == 200:
            # Success! Job was created
            logger.info(f"✅ Successfully dispatched call to {phone_number}")
            # Try to get job ID from JSON if available
            try:
                result = response.json()
                job_id = result.get("job", {}).get("id", "created")
                logger.info(f"Job ID: {job_id}")
                return job_id
            except (json.JSONDecodeError, ValueError):
                # Response is just "OK" - that's fine, job was created
                logger.info("Job created successfully (response: OK)")
                return "created"
        else:
            logger.error(f"❌ Unexpected response: {response_text}")
            return None
    
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response text: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Error dispatching to LiveKit: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def update_sheet_cell(service, row_number: int, column_name: str, value: str):
    """Update a specific cell in Google Sheets."""
    try:
        # Get headers to find column index
        range_name = f"{SHEET_NAME}!A1:Z1"
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name
        ).execute()
        
        headers = result.get("values", [])[0] if result.get("values") else []
        col_idx = get_column_index(headers, column_name)
        
        if col_idx is None:
            logger.warning(f"Column '{column_name}' not found in sheet")
            return
        
        # Convert to column letter (A=0, B=1, C=2, etc.)
        status_col = chr(65 + col_idx) if col_idx < 26 else chr(64 + (col_idx // 26)) + chr(65 + (col_idx % 26))
        
        # Update the cell
        range_to_update = f"{SHEET_NAME}!{status_col}{row_number}"
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_update,
            valueInputOption="RAW",
            body={"values": [[value]]}
        ).execute()
        
        logger.debug(f"Updated {column_name} in row {row_number} to: {value}")
    
    except Exception as e:
        logger.error(f"Error updating sheet cell: {e}")


def update_sheet_multiple_cells(service, row_number: int, updates: Dict[str, str]):
    """Update multiple cells in a row at once."""
    try:
        # Get headers to find column indices
        range_name = f"{SHEET_NAME}!A1:Z1"
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name
        ).execute()
        
        headers = result.get("values", [])[0] if result.get("values") else []
        
        # Build update ranges
        update_data = []
        for column_name, value in updates.items():
            col_idx = get_column_index(headers, column_name)
            if col_idx is not None:
                # Convert to column letter
                if col_idx < 26:
                    col_letter = chr(65 + col_idx)
                else:
                    col_letter = chr(64 + (col_idx // 26)) + chr(65 + (col_idx % 26))
                
                range_to_update = f"{SHEET_NAME}!{col_letter}{row_number}"
                update_data.append({
                    "range": range_to_update,
                    "values": [[value]]
                })
        
        if not update_data:
            logger.warning("No valid columns to update")
            return
        
        # Batch update
        body = {
            "valueInputOption": "RAW",
            "data": update_data
        }
        
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body=body
        ).execute()
        
        logger.info(f"Updated row {row_number}: {', '.join(updates.keys())}")
    
    except Exception as e:
        logger.error(f"Error updating multiple cells: {e}")


def check_call_status(service, row_number: int) -> Optional[str]:
    """Check the current status of a call in Google Sheets."""
    try:
        # Get headers to find Status column
        range_name = f"{SHEET_NAME}!A1:Z1"
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name
        ).execute()
        
        headers = result.get("values", [])[0] if result.get("values") else []
        status_idx = get_column_index(headers, "Status")
        
        if status_idx is None:
            return None
        
        # Get the status for this row
        if status_idx < 26:
            status_col = chr(65 + status_idx)
        else:
            status_col = chr(64 + (status_idx // 26)) + chr(65 + (status_idx % 26))
        range_to_read = f"{SHEET_NAME}!{status_col}{row_number}"
        
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_read
        ).execute()
        
        values = result.get("values", [])
        if values and len(values) > 0 and len(values[0]) > 0:
            return values[0][0].strip()
        
        return None
    except Exception as e:
        logger.debug(f"Error checking call status: {e}")
        return None


def wait_for_call_completion(service, row_number: int, phone_number: str) -> bool:
    """Wait for a call to complete by checking Google Sheets status.
    
    Returns True if call completed, False if timeout or error.
    """
    if not WAIT_FOR_CALL_COMPLETION:
        return True  # Don't wait if disabled
    
    logger.info(f"⏳ Waiting for call to {phone_number} to complete...")
    start_time = time.time()
    check_count = 0
    
    while True:
        elapsed = time.time() - start_time
        
        # Check if we've exceeded max wait time
        if elapsed > MAX_WAIT_TIME:
            logger.warning(f"⏱️  Max wait time ({MAX_WAIT_TIME}s) exceeded for {phone_number}")
            return False
        
        # Check status in Google Sheet
        status = check_call_status(service, row_number)
        check_count += 1
        
        if status:
            status_lower = status.lower()
            # Call is complete if status changed from "Dispatched"
            if status_lower in ["completed", "voicemail", "failed", "no answer", "hung up"]:
                logger.info(f"✅ Call to {phone_number} completed with status: {status} (waited {int(elapsed)}s)")
                if status_lower == "voicemail":
                    logger.info(f"📞 Voicemail detected - moving to next call in list")
                return True
            elif status_lower == "dispatched":
                # Still in progress
                if check_count % 6 == 0:  # Log every 6 checks (every minute if checking every 10s)
                    logger.info(f"⏳ Call to {phone_number} still in progress... ({int(elapsed)}s elapsed)")
        
        # Wait before next check
        time.sleep(CALL_COMPLETION_CHECK_INTERVAL)


def process_calls(service, pending_rows: List[Dict[str, Any]]):
    """Process calls one at a time, waiting for each to complete."""
    total = len(pending_rows)
    successful = 0
    failed = 0
    
    logger.info(f"Starting to process {total} calls...")
    if WAIT_FOR_CALL_COMPLETION:
        logger.info(f"⏳ Will wait for each call to complete before starting next (checks every {CALL_COMPLETION_CHECK_INTERVAL}s)")
    else:
        logger.info(f"⚡ Will dispatch all calls quickly (not waiting for completion)")
    
    for idx, row_data in enumerate(pending_rows, 1):
        phone_number = row_data["phone_number"]
        row_number = row_data["row_number"]
        
        is_retry = row_data.get("is_retry", False)
        retry_count = row_data.get("retry_count", 0)
        retry_label = f" (Retry #{retry_count})" if is_retry else ""
        logger.info(f"\n[{idx}/{total}] Processing call to {phone_number} (Row {row_number}){retry_label}...")
        
        # Update status to "Dispatched"
        update_sheet_cell(service, row_number, "Status", "Dispatched")
        update_sheet_cell(service, row_number, "Last Called", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # Update retry count if this is a retry
        if is_retry and retry_count > 0:
            update_sheet_cell(service, row_number, "Retry Count", str(retry_count))
        
        # Dispatch to LiveKit (try CLI first, fallback to HTTP)
        job_id = dispatch_to_livekit_cli(row_data)
        
        if job_id:
            successful += 1
            logger.info(f"✓ Call dispatched successfully. Job ID: {job_id}")
            
            # Wait for call to complete before next (if enabled)
            if WAIT_FOR_CALL_COMPLETION and idx < total:
                call_completed = wait_for_call_completion(service, row_number, phone_number)
                if not call_completed:
                    logger.warning(f"⚠️  Call to {phone_number} may still be in progress, but moving to next call")
            
            # Short delay before next call (even if waiting for completion)
            if idx < total:
                if not WAIT_FOR_CALL_COMPLETION:
                    logger.info(f"Waiting {CALL_DELAY_SECONDS} seconds before next call...")
                    time.sleep(CALL_DELAY_SECONDS)
                else:
                    logger.info(f"Call completed, proceeding to next...")
        else:
            failed += 1
            logger.error(f"✗ Failed to dispatch call")
            update_sheet_cell(service, row_number, "Status", "Failed")
    
    logger.info(f"\n=== Summary ===")
    logger.info(f"Total calls: {total}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")


def main():
    """Main function to process pending calls."""
    logger.info("=" * 60)
    logger.info("LiveKit Call Dispatcher")
    if USE_LOCAL_AGENT:
        logger.info("📍 Mode: LOCAL AGENT (ensure 'python agent.py dev' is running)")
    else:
        logger.info("☁️  Mode: CLOUD AGENT")
    logger.info("=" * 60)
    
    # Validate environment variables
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        logger.error("Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET in .env.local")
        logger.error("Please add these to your .env.local file")
        return
    
    if not LIVEKIT_URL:
        logger.error("Missing LIVEKIT_URL in .env.local")
        return
    
    # Get Google Sheets service
    try:
        logger.info("Authenticating with Google Sheets...")
        service = get_google_sheets_service()
        logger.info("✓ Google Sheets authentication successful")
    except Exception as e:
        logger.error(f"✗ Failed to authenticate with Google Sheets: {e}")
        return
    
    # Read pending rows
    logger.info(f"Reading pending rows from sheet: {SPREADSHEET_ID}")
    pending_rows = read_pending_rows(service)
    
    if not pending_rows:
        logger.info("No pending calls to dispatch")
        return
    
    # Process calls
    process_calls(service, pending_rows)
    
    logger.info("=" * 60)
    logger.info("Call dispatch process completed")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

