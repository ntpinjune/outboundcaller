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
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "5"))
PARALLEL_DIALING_ENABLED = os.getenv("PARALLEL_DIALING_ENABLED", "true").lower() == "true"
CALL_START_DELAY = float(os.getenv("CALL_START_DELAY", "0.5"))  # Delay between starting calls
CALL_COMPLETION_CHECK_INTERVAL = int(os.getenv("CALL_COMPLETION_CHECK_INTERVAL", "10"))
MONITOR_CALLS = os.getenv("MONITOR_CALLS", "true").lower() == "true"  # Monitor call completion

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("parallel-dispatch")

# Thread pool for synchronous operations
executor = ThreadPoolExecutor(max_workers=10)

# Track active calls
active_calls: Dict[int, Dict[str, Any]] = {}


async def dispatch_call_async(service, row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a single call asynchronously.
    
    Returns:
        Dict with success status, row_number, phone_number, and job_id
    """
    row_number = row_data["row_number"]
    phone_number = row_data["phone_number"]
    
    try:
        # Update status to "Dispatched" (synchronous operation in thread pool)
        await asyncio.get_event_loop().run_in_executor(
            executor,
            update_sheet_cell,
            service,
            row_number,
            "Status",
            "Dispatched"
        )
        
        await asyncio.get_event_loop().run_in_executor(
            executor,
            update_sheet_cell,
            service,
            row_number,
            "Last Called",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # Dispatch to LiveKit (synchronous operation)
        job_id = await asyncio.get_event_loop().run_in_executor(
            executor,
            dispatch_to_livekit_cli,
            row_data
        )
        
        if job_id:
            logger.info(f"✅ [{row_number}] Dispatched call to {phone_number}")
            
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
            await asyncio.get_event_loop().run_in_executor(
                executor,
                update_sheet_cell,
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
        try:
            await asyncio.get_event_loop().run_in_executor(
                executor,
                update_sheet_cell,
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
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
    
    async def dispatch_with_limit(row_data: Dict[str, Any], index: int):
        """Dispatch a call with concurrency limit."""
        async with semaphore:
            # Stagger call starts to avoid overwhelming the system
            if index > 0:
                await asyncio.sleep(CALL_START_DELAY * index)
            
            result = await dispatch_call_async(service, row_data)
            
            # Optionally monitor call completion
            if MONITOR_CALLS and result.get("success"):
                # Start monitoring in background (don't await)
                asyncio.create_task(
                    monitor_call_status(
                        service,
                        result["row_number"],
                        result["phone_number"]
                    )
                )
            
            return result
    
    # Create tasks for all calls
    tasks = [
        dispatch_with_limit(row_data, idx)
        for idx, row_data in enumerate(pending_rows)
    ]
    
    # Execute all calls concurrently (with semaphore limit)
    logger.info(f"📞 Dispatching {total} calls (max {MAX_CONCURRENT_CALLS} concurrent)...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
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
    
    if active_calls and MONITOR_CALLS:
        logger.info(f"\n⏳ Monitoring {len(active_calls)} active calls...")
        logger.info("   (Calls will update Google Sheets automatically when they complete)")


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




