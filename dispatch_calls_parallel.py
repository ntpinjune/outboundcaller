#!/usr/bin/env python3
"""
Parallel dispatch for outbound calls from Google Sheets to LiveKit.

This version dispatches multiple calls concurrently, dramatically increasing throughput.
"""

import os
import json
import logging
import asyncio
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Import from existing dispatch_calls.py
from dispatch_calls import (
    get_google_sheets_service,
    read_pending_rows,
    dispatch_to_livekit_cli,
    dispatch_to_livekit_http,
    update_sheet_cell,
    check_call_status,
    normalize_phone_number,
    SPREADSHEET_ID,
    SHEET_NAME,
    AGENT_NAME,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    LIVEKIT_URL,
)

# Load environment variables
load_dotenv(dotenv_path=".env.local")

# Parallel dialing configuration
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "3"))  # Default to 3 for simplicity
PARALLEL_DIALING_ENABLED = os.getenv("PARALLEL_DIALING_ENABLED", "true").lower() == "true"
CALL_START_DELAY = float(os.getenv("CALL_START_DELAY", "1.0"))  # Increased delay to avoid overwhelming
SKIP_SHEETS_UPDATES_DURING_DISPATCH = os.getenv("SKIP_SHEETS_UPDATES_DURING_DISPATCH", "false").lower() == "true"  # Enable updates by default now that we have safe locking

logging.basicConfig(
    level=logging.INFO,
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
        print(json.dumps(event), flush=True)
    except Exception as e:
        logger.error(f"Failed to emit UI event: {e}")


# Thread pool for synchronous operations
executor = ThreadPoolExecutor(max_workers=10)

# Lock to serialize Google Sheets API calls (Google Sheets client is NOT thread-safe)
# This prevents segmentation faults from concurrent access
sheets_api_lock = asyncio.Lock()


import signal

# Global flag for graceful shutdown
keep_running = True

def signal_handler(sig, frame):
    """Handle termination signals."""
    global keep_running
    logger.info("🛑 Received termination signal! Stopping dispatcher...")
    keep_running = False

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Semaphore to limit concurrent Google Sheets API calls (not thread-safe)
# Limit to 1 concurrent update to avoid SSL/connection issues and segfaults
sheets_api_semaphore = asyncio.Semaphore(1)


# Track active calls
active_calls: Dict[int, Dict[str, Any]] = {}


async def update_sheet_cell_safe(service, row_number: int, column: str, value: str, max_retries: int = 5):
    """Update a Google Sheets cell with retry logic and rate limiting.
    
    Uses both a lock and semaphore to ensure thread-safety and prevent segfaults.
    """
    async with sheets_api_semaphore:  # Limit concurrent API calls
        async with sheets_api_lock:  # Serialize access to prevent segfaults
            for attempt in range(max_retries):
                try:
                    # Add timeout to prevent indefinite hanging (30 seconds)
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            executor,
                            update_sheet_cell,
                            service,
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
                        logger.warning(f"⚠️  Timeout updating {column} for row {row_number} (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
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
                            logger.warning(f"⚠️  {error_type} error updating {column} for row {row_number} (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            error_type = "SSL" if is_ssl_error else "Timeout"
                            logger.error(f"❌ {error_type} error updating {column} for row {row_number} after {max_retries} attempts: {e}")
                            return False
                    else:
                        # Non-retryable error, don't retry
                        logger.error(f"❌ Error updating {column} for row {row_number}: {e}")
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
                await update_sheet_cell_safe(
                    service,
                    row_number,
                    "Status",
                    "Dispatching..."
                )
             except Exception as e:
                logger.warning(f"⚠️  [{row_number}] Failed to update status to Dispatching: {e}")

        # Dispatch to LiveKit (synchronous operation)
        job_id = await asyncio.get_event_loop().run_in_executor(
            executor,
            dispatch_to_livekit_cli,
            row_data
        )
        
        if job_id:
            logger.info(f"✅ [{row_number}] Dispatched call to {phone_number}")
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
                logger.debug(f"📝 [{row_number}] Updated sheet: Status=Dispatched")
            except Exception as e:
                logger.warning(f"⚠️  [{row_number}] Failed to update sheet with Dispatched status: {e}")
            
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
            logger.error(f"❌ [{row_number}] Failed to dispatch call to {phone_number}")
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
            except:
                pass
        
        return {
            "success": False,
            "row_number": row_number,
            "phone_number": phone_number,
            "error": str(e)
        }


async def monitor_call_status(service, row_number: int, phone_number: str):
    """Monitor a single call's status until completion."""
    max_checks = 60  # Max 10 minutes (60 checks * 10 seconds)
    check_count = 0
    
    while check_count < max_checks:
        await asyncio.sleep(CALL_COMPLETION_CHECK_INTERVAL)
        check_count += 1
        
        try:
            # Use semaphore for status checks too
            async with sheets_api_semaphore:
                status = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    check_call_status,
                    service,
                    row_number
                )
            
            if status:
                status_lower = status.lower()
                if status_lower in ["completed", "voicemail", "failed", "no answer"]:
                    logger.info(f"✅ [{row_number}] Call to {phone_number} completed with status: {status}")
                    emit_ui_event("call_completed", {
                        "row_number": row_number,
                        "phone_number": phone_number,
                        "status": status
                    })
                    active_calls.pop(row_number, None)
                    return True
                elif status_lower == "dispatched":
                    # Still in progress
                    continue
        except Exception as e:
            logger.debug(f"Error checking status for row {row_number}: {e}")
    
    # Timeout
    logger.warning(f"⏱️  [{row_number}] Call to {phone_number} monitoring timed out")
    active_calls.pop(row_number, None)
    return False


async def process_calls_parallel(service, pending_rows: List[Dict[str, Any]]):
    """Process calls in parallel with concurrency limit."""
    total = len(pending_rows)
    logger.info(f"🚀 Starting parallel dispatch of {total} calls")
    logger.info(f"⚙️  Max concurrent calls: {MAX_CONCURRENT_CALLS}")
    logger.info(f"⏱️  Call start delay: {CALL_START_DELAY}s")
    
    if not PARALLEL_DIALING_ENABLED:
        logger.warning("⚠️  Parallel dialing is disabled. Set PARALLEL_DIALING_ENABLED=true")
        return
    
    # Semaphore to limit concurrent dispatches
    # This ensures only MAX_CONCURRENT_CALLS are dispatched at once
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
    
    async def dispatch_with_limit(row_data: Dict[str, Any], index: int):
        """Dispatch a call with concurrency limit."""
        async with semaphore:
            # Stagger call starts to avoid overwhelming the system and API rate limits
            if index > 0:
                delay = CALL_START_DELAY * (index % MAX_CONCURRENT_CALLS)
                await asyncio.sleep(delay)
            
            # Dispatch the call
            result = await dispatch_call_async(service, row_data)
            
            # Hold semaphore for minimum call duration to prevent too many active calls
            # This ensures we don't dispatch too many calls that all run simultaneously
            if result.get("success"):
                # Wait minimum time before releasing semaphore (simulates call being active)
                # This prevents dispatching 20 calls all at once
                min_hold_time = 20.0  # Hold semaphore for 20 seconds (typical call start time)
                await asyncio.sleep(min_hold_time)
            
            return result
    
    # Process calls in batches to maintain true concurrency limit
    # Instead of dispatching all at once, dispatch MAX_CONCURRENT_CALLS, wait, then next batch
    results = []
    for batch_start in range(0, total, MAX_CONCURRENT_CALLS):
        batch_end = min(batch_start + MAX_CONCURRENT_CALLS, total)
        batch = pending_rows[batch_start:batch_end]
        batch_num = (batch_start // MAX_CONCURRENT_CALLS) + 1
        total_batches = (total + MAX_CONCURRENT_CALLS - 1) // MAX_CONCURRENT_CALLS
        
        if not keep_running:
            logger.info("🛑 Stopping dispatch loop (signal received)")
            break
            
        logger.info(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} calls)...")
        
        # Dispatch this batch with semaphore limit
        batch_tasks = [
            dispatch_with_limit(row_data, batch_start + idx)
            for idx, row_data in enumerate(batch)
        ]
        
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        results.extend(batch_results)
        
        # Wait between batches to ensure previous calls have time to start
        if batch_end < total:
            if not keep_running:
                break
            wait_time = CALL_START_DELAY * MAX_CONCURRENT_CALLS
            logger.info(f"⏳ Waiting {wait_time}s before next batch...")
            await asyncio.sleep(wait_time)
    
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
    
    logger.info(f"\n📊 Dispatch Summary:")
    logger.info(f"   Total: {total}")
    logger.info(f"   ✅ Successful: {successful}")
    logger.info(f"   ❌ Failed: {failed}")
    logger.info(f"   🔄 Active: {len(active_calls)}")
    logger.info(f"\n✅ All calls dispatched! The agent will update Google Sheets automatically when calls complete.")
    logger.info(f"   (No need to monitor - each agent instance updates its own row when done)")


async def main_async():
    """Async main function."""
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
        logger.info("✅ Google Sheets authentication successful")
    except Exception as e:
        logger.error(f"❌ Failed to authenticate with Google Sheets: {e}")
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
    
    # Process calls in parallel
    await process_calls_parallel(service, pending_rows)
    
    logger.info("=" * 60)
    logger.info("Parallel dispatch process completed")
    logger.info("=" * 60)


def main():
    """Main entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()






