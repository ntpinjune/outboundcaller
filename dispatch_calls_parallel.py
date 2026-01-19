#!/usr/bin/env python3
"""
Parallel dispatch for outbound calls from Google Sheets to LiveKit.

This version dispatches multiple calls concurrently, dramatically increasing throughput.
"""

import os
import json
import logging
import asyncio
import signal
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Load environment variables from .env.local if it exists
# This ensures env vars are available before config is loaded or overridden
# WE USE override=True to ensure that changes in .env.local take effect immediately
load_dotenv(dotenv_path=".env.local", override=True)

# Import from existing dispatch_calls.py
from dispatch_calls import (
    get_google_sheets_service,
    read_pending_rows,
    dispatch_to_livekit_cli,
    dispatch_to_livekit_http,
    update_sheet_cell,
    check_call_status,
    normalize_phone_number,
    get_column_index,
    execute_with_retry,
    SPREADSHEET_ID,
    SHEET_NAME,
    AGENT_NAME,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    LIVEKIT_URL,
    CALL_COMPLETION_CHECK_INTERVAL,
    MAX_WAIT_TIME,
)

# Global status cache for batch monitoring
status_cache = {}

# Parallel dialing configuration - read from config.json first, then env var, then default
def _get_max_concurrent_calls():
    """Get max concurrent calls from config.json or environment."""
    try:
        import json
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                value = config.get("call_dispatch", {}).get("max_concurrent_calls")
                if value is not None:
                    return max(1, min(10, int(value)))
    except Exception:
        pass
    return int(os.getenv("MAX_CONCURRENT_CALLS", "3"))

MAX_CONCURRENT_CALLS = _get_max_concurrent_calls()
PARALLEL_DIALING_ENABLED = os.getenv("PARALLEL_DIALING_ENABLED", "true").lower() == "true"
CALL_START_DELAY = float(os.getenv("CALL_START_DELAY", "1.0"))  # Increased delay to avoid overwhelming
SKIP_SHEETS_UPDATES_DURING_DISPATCH = os.getenv("SKIP_SHEETS_UPDATES_DURING_DISPATCH", "false").lower() == "true"  # Enable updates by default now that we have safe locking

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("parallel-dispatch")

# Helper to emit events for web UI
def emit_ui_event(event_type: str, data: Dict[str, Any]):
    """Emit a JSON event to stdout for the web server to capture."""
    try:
        event = {
            "type": "ui_event",
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        import sys
        print(json.dumps(event), flush=True)
        sys.stdout.flush() # Extra flush for terminal safety
    except Exception as e:
        logger.error(f"[ERROR] Failed to emit UI event: {e}")


# Thread pool for synchronous operations
executor = ThreadPoolExecutor(max_workers=10)

# Global flag for graceful shutdown
keep_running = True

# Global locks and semaphores (initialized lazily to ensure correct event loop affinity)
sheets_api_lock = None
sheets_api_semaphore = None

def signal_handler(sig, frame):
    """Handle termination signals."""
    global keep_running
    logger.info("[STOP] Received termination signal! Stopping dispatcher...")
    keep_running = False

# Register signal handlers
try:
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
except Exception as e:
    logger.warning(f"[WARNING] Could not register signal handlers: {e}")


def _ensure_api_tools():
    """Ensure sheets_api_lock and sheets_api_semaphore are initialized."""
    global sheets_api_lock, sheets_api_semaphore
    if sheets_api_lock is None:
        sheets_api_lock = asyncio.Lock()
    if sheets_api_semaphore is None:
        sheets_api_semaphore = asyncio.Semaphore(1)
    return sheets_api_lock, sheets_api_semaphore


# Track active calls and dispatch pacing
active_calls: Dict[int, Dict[str, Any]] = {}
_last_dispatch_time: float = 0
_dispatch_pacing_lock = asyncio.Lock()


async def update_sheet_cell_safe(service, row_number: int, column: str, value: str, max_retries: int = 5):
    """Update a Google Sheets cell with retry logic and rate limiting."""
    lock, sem = _ensure_api_tools()
    
    async with sem:  # Limit concurrent API calls
        async with lock:  # Serialize access to prevent segfaults
            # Ensure we have a valid service object (build is NOT thread-safe for creds refresh)
            # Rebuilding it here ensures we are within the lock
            current_service = service
            if current_service is None:
                try:
                    current_service = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        get_google_sheets_service
                    )
                except Exception as e:
                    logger.error(f"[ERROR] Failed to build Google Sheets service: {e}")
                    return False

            for attempt in range(max_retries):
                try:
                    # Add timeout to prevent indefinite hanging (30 seconds)
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            executor,
                            update_sheet_cell,
                            current_service,
                            row_number,
                            column,
                            value
                        ),
                        timeout=30.0  # 30 second timeout
                    )
                    return True
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2.0  # Exponential backoff: 2s, 4s, 6s, 8s
                        logger.warning(f"[WARNING] Timeout updating {column} for row {row_number} (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ Timeout updating {column} for row {row_number} after {max_retries} attempts")
                        return False
                except Exception as e:
                    error_str = str(e).lower()
                    # Check if it's an SSL error or timeout error
                    is_ssl_error = "ssl" in error_str or "decryption" in error_str or "wrong_version" in error_str
                    is_timeout_error = "timeout" in error_str or "timed out" in error_str or "read operation" in error_str
                    
                    if is_ssl_error or is_timeout_error:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 2.0  # Exponential backoff: 2s, 4s, 6s, 8s
                            error_type = "SSL" if is_ssl_error else "Timeout"
                            logger.warning(f"[WARNING] {error_type} error updating {column} for row {row_number} (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            error_type = "SSL" if is_ssl_error else "Timeout"
                            logger.error(f"[ERROR] {error_type} error updating {column} for row {row_number} after {max_retries} attempts: {e}")
                            return False
                    else:
                        # Non-retryable error, don't retry
                        logger.error(f"[ERROR] Error updating {column} for row {row_number}: {e}")
                        return False
            return False


async def dispatch_call_async(service, row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a single call asynchronously.
    
    Returns:
        Dict with success status, row_number, phone_number, and job_id
    """
    row_number = row_data["row_number"]
    phone_number = row_data["phone_number"]
    
    emit_ui_event("call_starting", {
        "row_number": row_number,
        "phone_number": phone_number,
        "name": row_data.get("name", "Unknown")
    })
    
    try:
        # Update sheet to "Dispatching" BEFORE calling LiveKit to prevent duplicates
        if not SKIP_SHEETS_UPDATES_DURING_DISPATCH:
             try:
                logger.info(f"🔍 [{row_number}] Updating sheet to Dispatching...")
                await update_sheet_cell_safe(
                    service,
                    row_number,
                    "Status",
                    "Dispatching..."
                )
                logger.info(f"🔍 [{row_number}] Sheet updated to Dispatching")
             except Exception as e:
                logger.warning(f"⚠️  [{row_number}] Failed to update status to Dispatching: {e}")

        # Dispatch to LiveKit (synchronous operation)
        logger.info(f"🔍 [{row_number}] Calling dispatch_to_livekit_cli...")
        job_id = await asyncio.get_event_loop().run_in_executor(
            executor,
            dispatch_to_livekit_cli,
            row_data
        )
        logger.info(f"🔍 [{row_number}] dispatch_to_livekit_cli returned job_id: {job_id}")
        
        if job_id:
            logger.info(f"[SUCCESS] [{row_number}] Dispatched call to {phone_number}")
            emit_ui_event("call_dispatched", {
                "row_number": row_number,
                "phone_number": phone_number,
                "job_id": job_id
            })
            
            
            # Always update sheet with "Dispatched" status when call is successfully dispatched
            try:
                await update_sheet_cell_safe(
                    service,
                    row_number,
                    "Status",
                    "Dispatched"
                )
                await update_sheet_cell_safe(
                    service,
                    row_number,
                    "Last Called",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                logger.debug(f"[TRANSCRIPT] [{row_number}] Updated sheet: Status=Dispatched")
            except Exception as e:
                logger.warning(f"[WARNING] [{row_number}] Failed to update sheet with Dispatched status: {e}")
            
            # Track active call
            active_calls[row_number] = {
                "started_at": datetime.now(),
                "phone_number": phone_number,
                "job_id": job_id,
                "row_data": row_data
            }
            
            return {
                "success": True,
                "row_number": row_number,
                "phone_number": phone_number,
                "job_id": job_id
            }
        else:
            logger.error(f"[ERROR] [{row_number}] Failed to dispatch call to {phone_number}")
            emit_ui_event("call_failed", {
                "row_number": row_number,
                "phone_number": phone_number,
                "error": "Dispatch failed"
            })
            if not SKIP_SHEETS_UPDATES_DURING_DISPATCH:
                await update_sheet_cell_safe(
                service,
                row_number,
                "Status",
                "Failed"
            )
            await update_sheet_cell_safe(
                service,
                row_number,
                "Outcome Details",
                "Dispatch Failed - No Job ID returned"
            )
            return {
                "success": False,
                "row_number": row_number,
                "phone_number": phone_number,
                "error": "Dispatch failed"
            }
            
    except Exception as e:
        logger.error(f"❌ [{row_number}] Exception dispatching call: {e}")
        emit_ui_event("call_failed", {
            "row_number": row_number,
            "phone_number": phone_number,
            "error": str(e)
        })
        if not SKIP_SHEETS_UPDATES_DURING_DISPATCH:
            try:
                await update_sheet_cell_safe(
                    service,
                    row_number,
                    "Status",
                    "Failed"
                )
                await update_sheet_cell_safe(
                    service,
                    row_number,
                    "Outcome Details",
                    f"Dispatch Error: {str(e)}"
                )
            except:
                pass
        
        return {
            "success": False,
            "row_number": row_number,
            "phone_number": phone_number,
            "error": str(e)
        }



async def batch_status_monitor(service):
    """Periodically fetch statuses for ALL active calls in one batch request."""
    logger.info("📡 Starting centralized batch status monitor")
    
    status_col_letter = None
    
    while keep_running:
        try:
            # Wait for next check interval
            await asyncio.sleep(CALL_COMPLETION_CHECK_INTERVAL)
            
            if not active_calls:
                continue
                
            # Get list of active row numbers
            active_rows = list(active_calls.keys())
            if not active_rows:
                continue
                
            min_row = min(active_rows)
            max_row = max(active_rows)
            
            # Determine Status column if not yet known
            if not status_col_letter:
                _, sem = _ensure_api_tools()
                async with sem:
                    headers_result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            executor,
                            lambda: execute_with_retry(service.spreadsheets().values().get(
                                spreadsheetId=SPREADSHEET_ID,
                                range=f"'{SHEET_NAME}'!A1:Z1"
                            ))
                        ),
                        timeout=30.0
                    )
                headers = headers_result.get("values", [])[0] if headers_result.get("values") else []
                status_idx = get_column_index(headers, "Status")
                
                if status_idx is None:
                    logger.error("❌ Could not find 'Status' column for batch monitoring")
                    continue
                    
                # Convert to letter
                if status_idx < 26:
                    status_col_letter = chr(65 + status_idx)
                else:
                    status_col_letter = chr(64 + (status_idx // 26)) + chr(65 + (status_idx % 26))
                logger.info(f"📡 Found 'Status' column at {status_col_letter}")

            # Fetch range covering all active rows
            # e.g. 'Sheet1'!C20:C50
            read_range = f"'{SHEET_NAME}'!{status_col_letter}{min_row}:{status_col_letter}{max_row}"
            
            _, sem = _ensure_api_tools()
            async with sem:
                # Add timeout to batch status fetch
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        executor,
                        lambda: execute_with_retry(service.spreadsheets().values().get(
                            spreadsheetId=SPREADSHEET_ID,
                            range=read_range
                        ))
                    ),
                    timeout=30.0
                )
            
            values = result.get("values", [])
            if not values:
                logger.debug(f"📡 Batch monitor: No values returned for range {read_range}")
                continue
                
            # Update cache
            for i, row_val in enumerate(values):
                current_row = min_row + i
                if current_row in active_calls:
                    val = row_val[0] if row_val else ""
                    if val:
                        status_cache[current_row] = val.strip()
            
            logger.debug(f"📡 Batch updated {len(values)} statuses for rows {min_row}-{max_row}")
            
        except Exception as e:
            logger.error(f"Error in batch status monitor: {e}")
            await asyncio.sleep(5)  # Backoff on error


async def monitor_call_status(service, row_number: int, phone_number: str):
    """Monitor a single call's status using the shared batch cache with direct fallback."""
    max_checks = MAX_WAIT_TIME 
    check_count = 0
    last_direct_fetch = 0
    
    logger.info(f"⏳ [{row_number}] Monitoring call to {phone_number} (max {MAX_WAIT_TIME}s)...")
    
    while check_count < max_checks:
        await asyncio.sleep(1.0) # Check local cache every second
        check_count += 1
        
        try:
            # 1. Check local cache populated by batch monitor
            status = status_cache.get(row_number)
            
            # 2. Fallback: If no status in cache or every 30s, do a direct fetch to be safe
            now = asyncio.get_event_loop().time()
            if not status or (now - last_direct_fetch > 30.0):
                last_direct_fetch = now
                # We reuse check_call_status from dispatch_calls.py but wrap it for safety
                lock, sem = _ensure_api_tools()
                async with sem:
                    async with lock:
                        status = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(
                                executor,
                                check_call_status,
                                service,
                                row_number
                            ),
                            timeout=10.0
                        )
                if status:
                    status_cache[row_number] = status.strip()
            
            if status:
                status_lower = status.lower()
                # Consider call finished if status is one of these terminal states
                if status_lower in ["completed", "voicemail", "failed", "no answer", "hung up", "disconnected", "declined", "busy", "canceled"]:
                    logger.info(f"[SUCCESS] [{row_number}] Call to {phone_number} completed with status: {status}")
                    emit_ui_event("call_completed", {
                        "row_number": row_number,
                        "phone_number": phone_number,
                        "status": status
                    })
                    active_calls.pop(row_number, None)
                    # Cleanup cache
                    status_cache.pop(row_number, None)
                    return True
                elif status_lower == "dispatched":
                    # Still in progress
                    if check_count % 30 == 0: # Log every 30s
                        logger.debug(f"⏳ [{row_number}] Call to {phone_number} still in progress...")
                    continue
        except Exception as e:
            logger.debug(f"Error checking status for row {row_number}: {e}")
    
    # Timeout
    logger.warning(f"[TIMEOUT] [{row_number}] Call to {phone_number} monitoring timed out after {MAX_WAIT_TIME}s")
    active_calls.pop(row_number, None)
    status_cache.pop(row_number, None)
    return False


async def process_calls_parallel(service, pending_rows: List[Dict[str, Any]]):
    """Process calls in parallel with concurrency limit."""
    total = len(pending_rows)
    logger.info(f"[START] Starting parallel dispatch of {total} calls")
    logger.info(f"[CONFIG] Max concurrent calls: {MAX_CONCURRENT_CALLS}")
    logger.info(f"[CONFIG] Call start delay: {CALL_START_DELAY}s")
    
    if not PARALLEL_DIALING_ENABLED:
        logger.warning("[WARNING] Parallel dialing is disabled. Set PARALLEL_DIALING_ENABLED=true")
        return
    
    # Semaphore to limit concurrent dispatches
    # This ensures only MAX_CONCURRENT_CALLS are dispatched at once
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
    
    results = []

    async def status_update_loop():
        """Periodic status updates for the UI."""
        while keep_running:
            try:
                emit_ui_event("status_update", {
                    "active_calls_count": len(active_calls),
                    "total_calls": total,
                    "processed_calls": len(results),
                    "timestamp": datetime.datetime.now().isoformat()
                })
            except Exception as e:
                logger.debug(f"Error in status_update_loop: {e}")
            await asyncio.sleep(5)
    
    async def dispatch_with_limit(row_data: Dict[str, Any], index: int):
        """Dispatch a call with concurrency limit and strict pacing."""
        global _last_dispatch_time
        
        async with semaphore:
            # Enforce strict pacing between any two dispatches
            async with _dispatch_pacing_lock:
                now = asyncio.get_event_loop().time()
                time_since_last = now - _last_dispatch_time
                if time_since_last < CALL_START_DELAY:
                    wait_time = CALL_START_DELAY - time_since_last
                    logger.info(f"⏳ Pacing: Waiting {wait_time:.1f}s before next dispatch...")
                    await asyncio.sleep(wait_time)
                
                _last_dispatch_time = asyncio.get_event_loop().time()
            
            row_number = row_data["row_number"]
            phone_number = row_data["phone_number"]
            active_slots = MAX_CONCURRENT_CALLS - semaphore._value
            logger.info(f"🚀 [{row_number}] Dispatching to {phone_number} (Active slots: {active_slots}/{MAX_CONCURRENT_CALLS})")
            
            # Dispatch the call
            result = await dispatch_call_async(service, row_data)
            
            # CRITICAL: Wait for the call to actually finish before releasing the semaphore slot
            if result.get("success"):
                logger.info(f"⏳ [{row_number}] Call active - holding slot until completion...")
                await monitor_call_status(service, row_number, phone_number)
            
            return result
    
    # Start status update loop
    status_task = asyncio.create_task(status_update_loop())
    
    # Start centralized batch status monitor
    monitor_task = asyncio.create_task(batch_status_monitor(service))
    
    try:
        # Create a list of tasks for all rows
        # They will naturally start in order, and the semaphore will limit concurrency
        tasks = []
        for idx, row_data in enumerate(pending_rows):
            if not keep_running:
                break
            tasks.append(dispatch_with_limit(row_data, idx))
        
        # Monitor all tasks
        logger.debug(f"🔍 Waiting for {len(tasks)} tasks to complete...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Flatten results if needed (already flat from gather)
        logger.debug("🔍 All dispatch tasks finished")
    finally:
        # Cancel status update loop
        status_task.cancel()
        try:
            await status_task
        except asyncio.CancelledError:
            pass
    
    # Process results
    successful = 0
    failed = 0
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Call failed with exception: {result}")
            failed += 1
        elif result.get("success"):
            successful += 1
        else:
            failed += 1
    
    logger.info(f"\n[STATS] Dispatch Summary:")
    logger.info(f"   Total: {total}")
    logger.info(f"   [SUCCESS] Successful: {successful}")
    logger.info(f"   [ERROR] Failed: {failed}")
    logger.info(f"   [SYNC] Active: {len(active_calls)}")
    logger.info(f"\n[SUCCESS] All calls dispatched! The agent will update Google Sheets automatically when calls complete.")
    logger.info(f"   (No need to monitor - each agent instance updates its own row when done)")


async def main_async():
    """Async main function."""
    try:
        logger.info("=" * 60)
        logger.info("LiveKit Parallel Call Dispatcher")
        logger.info("=" * 60)
        
        # Validate environment variables
        if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
            logger.error("Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET in .env.local")
            return
        
        if not LIVEKIT_URL:
            logger.error("Missing LIVEKIT_URL in .env.local")
            return
        
        # Get Google Sheets service
        try:
            logger.info("Authenticating with Google Sheets...")
            service = await asyncio.get_event_loop().run_in_executor(
                executor,
                get_google_sheets_service
            )
            logger.info("[SUCCESS] Google Sheets authentication successful")
        except Exception as e:
            logger.error(f"[ERROR] Failed to authenticate with Google Sheets: {e}")
            return
        
        # Read pending rows
        logger.info(f"Reading pending rows from sheet: {SPREADSHEET_ID}")
        pending_rows = await asyncio.get_event_loop().run_in_executor(
            executor,
            read_pending_rows,
            service
        )
        
        if not pending_rows:
            logger.info("No pending calls to dispatch")
            return
        
        # CRITICAL: Sort rows by row_number to ensure we go strictly "down the rows"
        pending_rows.sort(key=lambda x: x.get("row_number", 0))
        logger.info(f"Ordered {len(pending_rows)} rows for sequential-parallel dispatch")
        
        # Process calls in parallel
        await process_calls_parallel(service, pending_rows)
        
        logger.info("=" * 60)
        logger.info("Parallel dispatch process completed")
        logger.info("=" * 60)
    except Exception as e:
        logger.critical(f"💥 CRITICAL ERROR in dispatcher main loop: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Clear active calls on exit
        active_calls.clear()


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Dispatcher stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error running dispatcher: {e}")


if __name__ == "__main__":
    main()






