import subprocess
import sys
import signal
import time
import os
import threading
from datetime import datetime

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
                
                # Print to console (strip newline since print adds one)
                try:
                    print(line_str, end="", flush=True)
                except UnicodeEncodeError:
                    # Fallback for Windows consoles: replace unprintable chars
                    safe_str = line_str.encode('ascii', 'replace').decode('ascii')
                    print(safe_str, end="", flush=True)
                
                # Write to file with timestamp (if not just a newline)
                if line_str.strip():
                    # Check if line already has a timestamp (LiveKit logs usually do)
                    # simplified: just append to file
                    f.write(line_str)
                    f.flush()
    except Exception as e:
        print(f"Logging error: {e}")

def run_dev():
    """
    Runs both the LiveKit agent and the Web Server in parallel.
    Captures output and logs it to application.log.
    """
    processes = []
    shutdown_flag = False
    log_threads = []
    
    log_file = "application.log"
    # Create/clear log file on start
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n=== Application Started at {datetime.now()} ===\n")
    
    def signal_handler(sig, frame):
        nonlocal shutdown_flag
        global log_shutdown
        if shutdown_flag:
            return
        shutdown_flag = True
        log_shutdown = True
        
        print("\nBytes recieved signal. Shutting down processes gracefully...")
        # On Windows, Ctrl+C is sent to all processes in the console group.
        # We should wait for them to exit naturally first.
        
        # Give them 5 seconds to clean up
        for _ in range(50):
            if all(p.poll() is not None for p in processes):
                print("All processes exited.")
                sys.exit(0)
            time.sleep(0.1)
            
        print("Timeout reached. Forcing termination...")
        for p in processes:
            if p.poll() is None:
                p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    python_executable = sys.executable

    print(f"Starting Agent and Web Server using {python_executable}...")
    print(f"Logging output to {os.path.abspath(log_file)}")

    # Force UTF-8 encoding for child processes to prevent Windows cp1252 errors
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        # Start Agent
        print("Starting Agent (agent.py dev)...")
        # Use unbuffered output for Python (-u)
        agent_process = subprocess.Popen(
            [python_executable, "-u", "agent.py", "dev"],
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Merge stderr into stdout
            env=env,
        )
        processes.append(agent_process)
        
        # Start logger thread for Agent
        t_agent = threading.Thread(target=log_output, args=(agent_process.stdout, "[AGENT] ", log_file))
        t_agent.daemon = True
        t_agent.start()
        log_threads.append(t_agent)

        # Start Web Server
        print("Starting Web Server (web_server.py)...")
        web_process = subprocess.Popen(
            [python_executable, "-u", "web_server.py"],
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        processes.append(web_process)
        
        # Start logger thread for Web Server
        t_web = threading.Thread(target=log_output, args=(web_process.stdout, "[WEB] ", log_file))
        t_web.daemon = True
        t_web.start()
        log_threads.append(t_web)
        
        print("Both processes started. Press Ctrl+C to stop.")
        
        # Wait for processes
        while not shutdown_flag:
            time.sleep(1)
            # Check if any process has exited unexpectedly
            for i, p in enumerate(processes):
                if p.poll() is not None and not shutdown_flag:
                    print(f"Process {i} exited with code {p.returncode}")
                    # If one dies, trigger shutdown
                    signal_handler(signal.SIGTERM, None)
                    return

    except Exception as e:
        print(f"Error occurred: {e}")
        signal_handler(signal.SIGTERM, None)

if __name__ == "__main__":
    run_dev()
