
import asyncio
import logging
import os
import sys
import json
import time
import datetime
import signal
import database
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("local-dispatch")

# Import shared dispatcher logic
try:
    from dispatch_calls import (
        dispatch_to_livekit_cli,
        normalize_phone_number,
        CALL_COMPLETION_CHECK_INTERVAL,
        MAX_WAIT_TIME
    )
    from config_manager import load_config
except ImportError:
    # Add parent directory to path if needed (though usually in same dir)
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from dispatch_calls import (
        dispatch_to_livekit_cli,
        normalize_phone_number,
        CALL_COMPLETION_CHECK_INTERVAL,
        MAX_WAIT_TIME
    )
    from config_manager import load_config


# --- Configuration ---
config = load_config()
call_dispatch_config = config.get("call_dispatch", {})

MAX_CONCURRENT_CALLS = int(
    call_dispatch_config.get("max_concurrent_calls") or 
    os.getenv("MAX_CONCURRENT_CALLS", "4")
)
CALL_START_DELAY = float(os.getenv("CALL_START_DELAY", "2.0")) # Delay between adding calls

# Global shutdown flag
keep_running = True


def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    global keep_running
    logger.info(f"Received signal {signum}. Shutting down...")
    keep_running = False

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


async def monitor_call_status(lead_id: int):
    """Monitor a single call's status in DB until completion."""
    check_count = 0
    max_checks = MAX_WAIT_TIME // 2 # Check every 2s
    
    logger.info(f"⏳ [{lead_id}] Monitoring call status...")
    
    while check_count < max_checks and keep_running:
        await asyncio.sleep(2.0)
        check_count += 1
        
        status = database.get_lead_status(lead_id)
        if not status:
            continue
            
        status_lower = status.lower()
        if status_lower in ["completed", "voicemail", "failed", "no answer", "hung up", "declined", "busy"]:
            logger.info(f"✅ [{lead_id}] Call completed with status: {status}")
            return True
        elif status_lower == "dispatching":
            # Wait for dispatch
            pass
        elif status_lower == "dispatched":
             # In progress
             if check_count % 10 == 0:
                 logger.debug(f"⏳ [{lead_id}] Call in progress...")
    
    return False


async def process_leads_parallel():
    """Process pending leads with parallel dispatch."""
    
    # Reload config just in case
    global MAX_CONCURRENT_CALLS
    config = load_config()
    MAX_CONCURRENT_CALLS = int(config.get("call_dispatch", {}).get("max_concurrent_calls", 4))
    
    logger.info(f"🚀 Starting Local Dispatcher (Concurrent: {MAX_CONCURRENT_CALLS})")
    
    # NEW: Reset any leads stuck in "Dispatching" to "Pending" on startup
    # This handles cases where a previous run was interrupted.
    try:
        conn = database.get_db()
        c = conn.cursor()
        c.execute("UPDATE leads SET status = 'Pending' WHERE status = 'Dispatching'")
        reset_count = c.rowcount
        conn.commit()
        conn.close()
        if reset_count > 0:
            logger.info(f"♻️  Reset {reset_count} leads from 'Dispatching' back to 'Pending'")
    except Exception as e:
        logger.error(f"Error resetting stuck leads: {e}")

    # Fetch all pending leads
    leads = database.get_pending_leads(limit=1000)
    
    if not leads:
        logger.info("No pending leads found.")
        return

    logger.info(f"Found {len(leads)} pending leads.")
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
    
    async def dispatch_lead(lead):
        if not keep_running:
            return
            
        async with semaphore:
            lead_id = lead['id']
            phone = lead['phone_number']
            
            # 1. Update status to Dispatching
            database.update_lead_status(lead_id, "Dispatching")
            
            # 2. Prepare Data
            row_data = {
                "row_id": str(lead_id), # Important: Pass as string
                "phone_number": phone,
                "name": lead['name'] or "",
                "business_name": lead['business_name'] or "",
                "appointment_time": lead['appointment_time'] or "",
                "source": "local", # Flag for agent to use local update path
                "row_number": lead_id # For logging compatibility
            }
            
            logger.info(f"📞 [{lead_id}] Dispatching to {phone}...")
            
            # 3. Dispatch
            # Fix: dispatch_to_livekit_cli is synchronous, so we use to_thread to avoid blocking
            # and it returns a string/None, not a dict.
            result = await asyncio.to_thread(dispatch_to_livekit_cli, row_data)
            
            if result:
                database.update_lead_status(lead_id, "Dispatched")
                # 4. Monitor
                await monitor_call_status(lead_id)
            else:
                logger.error(f"❌ [{lead_id}] Dispatch failed")
                database.update_lead_status(lead_id, "Failed")
            
            # Pacing
            await asyncio.sleep(CALL_START_DELAY)

    # Launch tasks
    tasks = []
    for lead in leads:
        if not keep_running:
            break
        task = asyncio.create_task(dispatch_lead(lead))
        tasks.append(task)
        # Verify keep_running periodically in main loop if needed, 
        # but here we just queue them all and let semaphore throttle.
        # Actually, for huge lists, queuing all at once is bad. 
        # But for <1000 it's fine.
    
    if tasks:
        await asyncio.gather(*tasks)
    
    logger.info("🏁 All tasks completed (or stopped).")


def main():
    asyncio.run(process_leads_parallel())

if __name__ == "__main__":
    main()
