import subprocess
import sys
import signal
import time
import os
import threading
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env.local", override=True)

# Import queue cleaner
from clear_queue import clear_queue

# Global flag for shutting down log threads
log_shutdown = False

def log_output(pipe, prefix, log_file):
    """Read from pipe and write to both stdout and log file."""
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            for line in iter(pipe.readline, b""):
                if log_shutdown:
                    break
                
                # Decode line
                try:
                    line_str = line.decode("utf-8")
                except:
                    line_str = str(line)
                
                # Print to console with prefix
                print(f"{prefix}{line_str}", end="", flush=True)
                
                # Write to file
                if line_str.strip():
                    f.write(f"{prefix}{line_str}")
                    f.flush()
    except Exception as e:
        print(f"Logging error: {e}")

def run_multi_agent():
    """
    Runs multiple LiveKit agent instances (one per account) and the Web Server.
    """
    processes = []
    shutdown_flag = False
    log_threads = []
    
    log_file = "application_multi.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n=== Multi-Agent Application Started at {datetime.now()} ===\n")
    
    # Load accounts
    accounts = []
    try:
        json_path = os.path.join(os.path.dirname(__file__), "livekit_accounts.json")
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                accounts = json.load(f)
            print(f"✅ Loaded {len(accounts)} LiveKit accounts.")
        else:
            print("ℹ️  No livekit_accounts.json found. Will run single default agent.")
    except Exception as e:
        print(f"❌ Error loading livekit_accounts.json: {e}")

    # Use default env vars if no accounts loaded
    if not accounts:
        accounts = [{
            "name": "Default",
            "url": os.getenv("LIVEKIT_URL"),
            "api_key": os.getenv("LIVEKIT_API_KEY"),
            "api_secret": os.getenv("LIVEKIT_API_SECRET")
        }]

    # --- CLEANUP ---
    clean_start = os.getenv("CLEAN_START", "true").lower() == "true"
    if clean_start:
        print("🧹 CLEAN_START: Clearing existing queues...")
        try:
            # We only clear queue for the default/first account for now as clear_queue script relies on env vars
            # TODO: Update clear_queue to handle multiple accounts if needed
            asyncio.run(clear_queue())
            print("✅ Queue cleared.")
        except Exception as e:
            print(f"⚠️  Failed to clear queue: {e}")

    def signal_handler(sig, frame):
        nonlocal shutdown_flag
        global log_shutdown
        if shutdown_flag:
            return
        shutdown_flag = True
        log_shutdown = True
        
        print("\n🛑 Shutting down all processes...")
        
        # Terminate all
        for p in processes:
            if p.poll() is None:
                p.terminate()
        
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    python_executable = sys.executable
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["OTEL_SDK_DISABLED"] = "true"

    try:
        # 1. Start Web Server (Shared)
        print("Starting Web Server...")
        web_process = subprocess.Popen(
            [python_executable, "-u", "web_server.py"],
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        processes.append(web_process)
        t_web = threading.Thread(target=log_output, args=(web_process.stdout, "[WEB] ", log_file))
        t_web.daemon = True
        t_web.start()
        log_threads.append(t_web)

        # 2. Start Agent for EACH account
        for i, account in enumerate(accounts):
            name = account.get("name", f"Account-{i+1}")
            print(f"Starting Agent for {name}...")
            
            # Create specific env
            agent_env = env.copy()
            if account.get("url"): agent_env["LIVEKIT_URL"] = account.get("url")
            if account.get("api_key"): agent_env["LIVEKIT_API_KEY"] = account.get("api_key")
            if account.get("api_secret"): agent_env["LIVEKIT_API_SECRET"] = account.get("api_secret")
            
            # Run agent
            agent_process = subprocess.Popen(
                [python_executable, "-u", "agent.py", "dev"],
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=agent_env,
            )
            processes.append(agent_process)
            
            # Log with prefix
            prefix = f"[{name}] "
            t_agent = threading.Thread(target=log_output, args=(agent_process.stdout, prefix, log_file))
            t_agent.daemon = True
            t_agent.start()
            log_threads.append(t_agent)
            
            # Stagger starts slightly to avoid hammering APIs
            time.sleep(2)

        print(f"🚀 All systems go! Running {len(accounts)} agents and 1 web server.")
        print("Press Ctrl+C to stop.")

        while not shutdown_flag:
            time.sleep(1)
            # Check if web server died (critical)
            if web_process.poll() is not None:
                print("❌ Web server exited unexpectedly. Shutting down.")
                signal_handler(signal.SIGTERM, None)
                return

    except Exception as e:
        print(f"Error: {e}")
        signal_handler(signal.SIGTERM, None)

if __name__ == "__main__":
    run_multi_agent()
