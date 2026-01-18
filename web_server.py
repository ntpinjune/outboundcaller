"""
Web Server for Outbound Caller Agent Configuration

Provides a REST API and web interface for configuring the agent without code changes.
"""

import os
import json
import logging
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from typing import Dict, Any, Optional
import subprocess
import threading
from datetime import datetime
import base64
import hmac
import hashlib
import base64
import hmac
import hashlib
import requests
from werkzeug.utils import secure_filename


# Import from dispatch_calls
# Make sure dispatch_calls.py is in the Python path
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dispatch_calls import get_google_sheets_service, read_pending_rows

from config_manager import load_config, save_config, get_config_value, load_system_prompt, get_effective_system_prompt

# Import call history for observability
try:
    from call_history import get_call_history, CallRecord, get_calls, get_call
    CALL_HISTORY_AVAILABLE = True
except ImportError:
    CALL_HISTORY_AVAILABLE = False
    logger.warning("Call history module not available")


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web-server")

# Ensure static/sounds directory exists
os.makedirs(os.path.join(os.path.dirname(__file__), 'static', 'sounds'), exist_ok=True)

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Configuration
PORT = int(os.getenv("WEB_SERVER_PORT", "5000"))
HOST = os.getenv("WEB_SERVER_HOST", "0.0.0.0")  # 0.0.0.0 = listen on all interfaces (accessible from network)

# Security: Basic authentication (set via environment variable)
WEB_SERVER_PASSWORD = os.getenv("WEB_SERVER_PASSWORD", "")  # Set this to require password


# Store for agent reload signal and background processes
_agent_reload_requested = False
_agent_reload_lock = threading.Lock()

# Store active dispatcher process
_dispatcher_process = None
_dispatcher_lock = threading.Lock()

# Event streaming
import queue
_event_subscribers = []  # List of Queue objects
_event_monitor_thread = None




def kill_process_tree(pid):
    """Kill a process tree (including children) on Windows."""
    try:
        import subprocess
        # Suppress output, check=True will raise CalledProcessError on failure
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)], 
            check=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        # Process likely already dead or not found, which is what we wanted
        return False
    except Exception as e:
        logger.error(f"Error killing process tree {pid}: {e}")
        return False


def check_auth():
    """Check if request is authenticated (if password is set)."""
    if not WEB_SERVER_PASSWORD:
        return True  # No password set, allow access
    
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Basic '):
        return False
    
    try:
        encoded = auth.split(' ', 1)[1]
        decoded = base64.b64decode(encoded).decode('utf-8')
        username, password = decoded.split(':', 1)
        return password == WEB_SERVER_PASSWORD
    except Exception:
        return False


@app.before_request
def require_auth():
    """Require authentication for API routes if password is set."""
    if WEB_SERVER_PASSWORD and request.path.startswith('/api/'):
        if not check_auth():
            return jsonify({
                "success": False,
                "error": "Authentication required"
            }), 401


@app.after_request
def add_header(response):
    """Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route('/')
def index():
    """Serve the main web interface."""
    return send_from_directory('static', 'index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    try:
        config = load_config()
        return jsonify({
            "success": True,
            "config": config
        })
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration."""
    try:
        data = request.json
        if not data or "config" not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'config' in request body"
            }), 400
        
        # Load current config
        current_config = load_config()
        
        # Merge with new config
        new_config = _deep_merge(current_config, data["config"])
        
        # Save to file
        if save_config(new_config):
            # Signal that agent should be reloaded
            global _agent_reload_requested
            with _agent_reload_lock:
                _agent_reload_requested = True
            
            return jsonify({
                "success": True,
                "message": "Configuration saved. Agent will pick up changes on next call (restart required for API keys)."
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save configuration"
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/config/schema', methods=['GET'])
def get_config_schema():
    """Get configuration schema for frontend validation."""
    from config_manager import CONFIG_SCHEMA
    return jsonify({
        "success": True,
        "schema": CONFIG_SCHEMA
    })


@app.route('/api/prompt', methods=['GET'])
def get_prompt():
    """Get current system prompt that the agent is actually using."""
    try:
        effective_prompt = get_effective_system_prompt()
        return jsonify({
            "success": True,
            "prompt": effective_prompt["prompt"],
            "source": effective_prompt["source"],
            "is_default": effective_prompt["is_default"]
        })
    except Exception as e:
        logger.error(f"Error loading prompt: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/prompt', methods=['POST'])
def update_prompt():
    """Update system prompt."""
    try:
        data = request.json
        if not data or "prompt" not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'prompt' in request body"
            }), 400
        
        # Load current config
        config = load_config()
        config["system_prompt"] = data["prompt"]
        
        # Save
        if save_config(config):
            # Signal that agent should be reloaded
            global _agent_reload_requested
            with _agent_reload_lock:
                _agent_reload_requested = True
            logger.info("System prompt updated and agent reload signaled")
            return jsonify({
                "success": True,
                "message": "System prompt updated successfully. Please restart the agent process to apply changes.",
                "reload_needed": True
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save prompt"
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating prompt: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/piper/voices', methods=['GET'])
def get_piper_voices():
    """List available Piper TTS voice models."""
    try:
        voices = []
        
        # Define paths to check
        paths_to_check = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "piper1-gpl"),
            os.path.dirname(os.path.abspath(__file__))
        ]
        
        # Helper to check directory
        def scan_dir(directory):
            if not os.path.exists(directory):
                return
            
            for file in os.listdir(directory):
                if file.endswith(".onnx"):
                    # Found a model
                    model_path = os.path.join(directory, file)
                    config_path = model_path + ".json"
                    
                    # Create readable name
                    name = file.replace(".onnx", "").replace("-", " ").title()
                    if "En Us" in name:
                        name = name.replace("En Us", "English (US)")
                        
                    voice_entry = {
                        "name": name,
                        "model_path": model_path,
                        "config_path": config_path if os.path.exists(config_path) else "",
                        "filename": file
                    }
                    
                    # Avoid duplicates
                    if not any(v["filename"] == file for v in voices):
                        voices.append(voice_entry)

        for path in paths_to_check:
            scan_dir(path)
            
        return jsonify({
            "success": True,
            "voices": voices
        })
            
    except Exception as e:
        logger.error(f"Error listing Piper voices: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


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
    
    config = load_config()
    livekit_api_key = config["integrations"]["livekit_api_key"] or os.getenv("LIVEKIT_API_KEY", "")
    livekit_api_secret = config["integrations"]["livekit_api_secret"] or os.getenv("LIVEKIT_API_SECRET", "")
    
    if not livekit_api_key or not livekit_api_secret:
        raise ValueError("LiveKit API key and secret are required")
    
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": livekit_api_key,
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
        livekit_api_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def dispatch_to_livekit_http(phone_number: str, name: str = "Test Customer", appointment_time: str = "", business_name: str = "") -> Optional[str]:
    """Dispatch a call to LiveKit using HTTP API."""
    try:
        config = load_config()
        livekit_url_raw = config["integrations"]["livekit_url"] or os.getenv("LIVEKIT_URL", "")
        livekit_url = livekit_url_raw.replace("wss://", "https://").replace("ws://", "http://")
        agent_name = os.getenv("AGENT_NAME", "outbound-caller-dev")
        
        if not livekit_url:
            raise ValueError("LiveKit URL is required")
        
        # Normalize phone number
        phone_number = normalize_phone_number(phone_number)
        
        # Prepare metadata
        metadata = {
            "phone_number": phone_number,
            "name": name,
            "appointment_time": appointment_time,
            "business_name": business_name,
            "row_id": "test_call"
        }
        
        # Generate JWT token
        jwt_token = generate_livekit_jwt()
        
        # Make API request
        url = f"{livekit_url}/twirp/livekit.AgentService/CreateJob"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "job": {
                "agent_name": agent_name,
                "room_name": "",  # Empty = create new room
                "metadata": json.dumps(metadata)
            }
        }
        
        logger.info(f"Dispatching test call to {phone_number} via HTTP API")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully dispatched test call to {phone_number}")
            try:
                result = response.json()
                job_id = result.get("job", {}).get("id", "created")
                return job_id
            except (json.JSONDecodeError, ValueError):
                return "created"
        else:
            logger.error(f"❌ LiveKit API returned status {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error dispatching call via HTTP: {e}")
        return None


def dispatch_to_livekit_cli(phone_number: str, name: str = "Test Customer", appointment_time: str = "", business_name: str = "") -> Optional[str]:
    """Dispatch a call to LiveKit using CLI."""
    try:
        agent_name = os.getenv("AGENT_NAME", "outbound-caller-dev")
        phone_number = normalize_phone_number(phone_number)
        
        # Prepare metadata
        metadata = {
            "phone_number": phone_number,
            "name": name,
            "appointment_time": appointment_time,
            "business_name": business_name,
            "row_id": "test_call"
        }
        
        # Build CLI command
        cmd = [
            "lk", "dispatch", "create",
            "--new-room",
            "--agent-name", agent_name,
            "--metadata", json.dumps(metadata)
        ]
        
        logger.info(f"Dispatching test call to {phone_number} via CLI")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Successfully dispatched test call to {phone_number} via CLI")
            return "created"
        else:
            logger.warning(f"CLI dispatch failed: {result.stderr}")
            return None
            
    except FileNotFoundError:
        logger.warning("LiveKit CLI not found, falling back to HTTP API")
        return None
    except Exception as e:
        logger.error(f"Error dispatching call via CLI: {e}")
        return None


@app.route('/api/calls/dispatch', methods=['POST'])
def dispatch_call():
    """Dispatch a test call with current configuration."""
    try:
        data = request.json or {}
        phone_number = data.get("phone_number", "").strip()
        name = data.get("name", "Test Customer").strip() or "Test Customer"
        appointment_time = data.get("appointment_time", "").strip()
        business_name = data.get("business_name", "").strip()
        
        if not phone_number:
            return jsonify({
                "success": False,
                "error": "phone_number is required"
            }), 400
        
        # Try CLI first, fallback to HTTP
        job_id = dispatch_to_livekit_cli(phone_number, name, appointment_time, business_name)
        if not job_id:
            logger.info("CLI dispatch failed or not available, trying HTTP API...")
            job_id = dispatch_to_livekit_http(phone_number, name, appointment_time, business_name)
        
        if job_id:
            return jsonify({
                "success": True,
                "message": f"Test call dispatched successfully to {phone_number}",
                "job_id": job_id
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to dispatch call. Check LiveKit configuration and ensure agent is running."
            }), 500
        
    except Exception as e:
        logger.error(f"Error dispatching call: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500




@app.route('/api/calls/preview', methods=['GET'])
def preview_pending_calls():
    """Get list of pending calls from Google Sheets."""
    try:
        service = get_google_sheets_service()
        pending_rows = read_pending_rows(service)
        
        return jsonify({
            "success": True,
            "count": len(pending_rows),
            "calls": pending_rows
        })
        
    except Exception as e:
        logger.error(f"Error previewing calls: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500



def _monitor_dispatcher_output(process):
    """Monitor output from dispatcher process and broadcast to subscribers."""
    try:
        # Read line by line
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
                
            line = line.strip()
            if not line:
                continue
                
            # Try to parse as JSON event
            event_data = None
            try:
                if line.startswith('{') and 'ui_event' in line:
                    data = json.loads(line)
                    if data.get("type") == "ui_event":
                        event_data = data
            except:
                pass
                
            # If not a structured event, treat as log
            if not event_data:
                event_data = {
                    "type": "log",
                    "timestamp": datetime.now().isoformat(),
                    "message": line
                }
            
            # Broadcast to all subscribers
            dead_queues = []
            for q in _event_subscribers:
                try:
                    q.put_nowait(event_data)
                except queue.Full:
                    dead_queues.append(q)
                except Exception:
                    dead_queues.append(q)
            
            # cleanup
            for q in dead_queues:
                if q in _event_subscribers:
                    _event_subscribers.remove(q)
                    
    except Exception as e:
        logger.error(f"Error monitoring dispatcher: {e}")
    finally:
        # Send finished event
        return_code = process.poll()
        final_event = {
            "type": "control",
            "timestamp": datetime.now().isoformat(),
            "event": "process_ended",
            "return_code": return_code
        }
        for q in _event_subscribers:
            try:
                q.put_nowait(final_event)
            except:
                pass


@app.route('/api/calls/parallel/events')
def stream_dispatcher_events():
    """Stream events from the dispatcher process via SSE."""
    def gen():
        q = queue.Queue()
        _event_subscribers.append(q)
        try:
            # Send initial connected event
            yield f"data: {json.dumps({'type': 'control', 'event': 'connected'})}\n\n"
            
            while True:
                try:
                    # Get event from queue (timeout to allow checking for disconnect)
                    event = q.get(timeout=1.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    # Keep alive
                    yield f": keep-alive\n\n"
        except GeneratorExit:
            if q in _event_subscribers:
                _event_subscribers.remove(q)
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            if q in _event_subscribers:
                _event_subscribers.remove(q)
                
    return app.response_class(gen(), mimetype='text/event-stream')


@app.route('/api/calls/dispatch-parallel', methods=['POST'])
def dispatch_parallel_calls():
    """Trigger parallel dispatch of calls from Google Sheets."""
    global _dispatcher_process
    
    try:
        # Check if already running
        with _dispatcher_lock:
            if _dispatcher_process and _dispatcher_process.poll() is None:
                return jsonify({
                    "success": False,
                    "error": "Dispatcher is already running",
                    "pid": _dispatcher_process.pid
                }), 409

            script_path = os.path.join(os.path.dirname(__file__), "dispatch_calls_parallel.py")
            if not os.path.exists(script_path):
                 return jsonify({
                    "success": False,
                    "error": "dispatch_calls_parallel.py not found"
                }), 404
    
            # Run in background
            import sys
            
            # Force UTF-8 encoding and unbuffered output for child process to prevent Windows errors
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"

            # Use Popen to run in background
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                encoding="utf-8",
                bufsize=1,  # Line buffered
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                env=env
            )
            
            _dispatcher_process = process
            
            # Start monitoring thread
            global _event_monitor_thread
            _event_monitor_thread = threading.Thread(
                target=_monitor_dispatcher_output,
                args=(process,),
                daemon=True
            )
            _event_monitor_thread.start()
        
        return jsonify({
            "success": True,
            "message": "Parallel call dispatch started",
            "pid": process.pid
        })
        
    except Exception as e:
        logger.error(f"Error starting parallel dispatch: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/calls/stop-parallel', methods=['POST'])
def stop_parallel_calls():
    """Stop the running parallel dispatcher."""
    global _dispatcher_process
    
    try:
        with _dispatcher_lock:
            if not _dispatcher_process:
                return jsonify({
                    "success": False,
                    "error": "No dispatcher process running"
                }), 404
            
            if _dispatcher_process.poll() is not None:
                _dispatcher_process = None
                return jsonify({
                    "success": False,
                    "error": "Dispatcher process already finished"
                }), 409
            
            # Kill the process tree logic
            pid = _dispatcher_process.pid
            
            # Try gentle terminate first
            _dispatcher_process.terminate()
            
            # Use taskkill for force if needed (on Windows)
            if os.name == 'nt':
                 kill_process_tree(pid)
            
            _dispatcher_process = None
            
        return jsonify({
            "success": True,
            "message": f"Stopped dispatcher process {pid}"
        })
        
    except Exception as e:
        logger.error(f"Error stopping dispatcher: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500



@app.route('/api/test/connection', methods=['POST'])
def test_connection():
    """Test LiveKit connection."""
    try:
        config = load_config()
        livekit_url = config["integrations"]["livekit_url"] or os.getenv("LIVEKIT_URL", "")
        livekit_api_key = config["integrations"]["livekit_api_key"] or os.getenv("LIVEKIT_API_KEY", "")
        
        if not livekit_url or not livekit_api_key:
            return jsonify({
                "success": False,
                "error": "LiveKit URL and API key are required"
            }), 400
        
        # Simple validation - in production, make actual API call
        return jsonify({
            "success": True,
            "message": "LiveKit credentials configured",
            "url": livekit_url
        })
        
    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/agent/reload', methods=['POST'])
def reload_agent():
    """Signal that agent should reload configuration (requires manual restart)."""
    global _agent_reload_requested
    
    try:
        with _agent_reload_lock:
            _agent_reload_requested = True
        
        logger.info("Agent reload requested via web interface")
        
        return jsonify({
            "success": True,
            "message": "Agent reload requested. Please restart the agent process manually to apply changes.",
            "note": "The agent process needs to be restarted for configuration changes to take effect."
        })
    except Exception as e:
        logger.error(f"Error requesting agent reload: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/agent/status', methods=['GET'])
def agent_status():
    """Get agent status and reload request status."""
    global _agent_reload_requested
    
    with _agent_reload_lock:
        reload_requested = _agent_reload_requested
        if reload_requested:
            _agent_reload_requested = False  # Reset after reading
    
    return jsonify({
        "success": True,
        "reload_requested": reload_requested,
        "message": "Reload requested - restart agent to apply changes" if reload_requested else "Agent running normally"
    })



@app.route('/api/agent/start', methods=['POST'])
def start_agent():
    """Start the LiveKit agent in a new terminal window."""
    try:
        script_path = os.path.join(os.path.dirname(__file__), "agent.py")
        if not os.path.exists(script_path):
             return jsonify({
                "success": False,
                "error": "agent.py not found"
            }), 404

        import sys
        import platform
        
        # Command to run (using the same python executable as web_server)
        cmd = [sys.executable, script_path, "dev"]
        
        # On Windows, open in a new console window so user can see logs
        if os.name == 'nt':
            # CREATE_NEW_CONSOLE = 0x00000010
            process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                close_fds=True
            )
            message = "Agent started in new terminal window"
        else:
            # On generic Linux/Mac, just run in background
            # A more advanced implementation might use xterm/gnome-terminal
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            message = "Agent started in background"
            
        return jsonify({
            "success": True,
            "message": message,
            "pid": process.pid
        })
        
    except Exception as e:
        logger.error(f"Error starting agent: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ===== Call History API Endpoints =====

@app.route('/call-history')
def call_history_page():
    """Serve the call history dashboard page."""
    return send_from_directory(app.static_folder, 'call_history.html')


@app.route('/api/calls', methods=['GET'])
def list_calls():
    """List call history with optional filtering."""
    if not CALL_HISTORY_AVAILABLE:
        return jsonify({"error": "Call history not available"}), 503
    
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        status = request.args.get('status')
        phone = request.args.get('phone')
        
        calls = get_calls(
            limit=limit,
            offset=offset,
            status=status if status else None,
            phone_number=phone if phone else None
        )
        
        call_history = get_call_history()
        total = call_history.get_call_count(status=status if status else None)
        
        return jsonify({
            "success": True,
            "calls": [c.to_dict() for c in calls],
            "total": total,
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        logger.error(f"Error listing calls: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/calls/<room_id>', methods=['GET'])
def get_call_details(room_id):
    """Get details of a single call."""
    if not CALL_HISTORY_AVAILABLE:
        return jsonify({"error": "Call history not available"}), 503
    
    try:
        call = get_call(room_id)
        if call:
            return jsonify({
                "success": True,
                "call": call.to_dict()
            })
        else:
            return jsonify({"success": False, "error": "Call not found"}), 404
    except Exception as e:
        logger.error(f"Error getting call details: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/calls/<room_id>/audio', methods=['GET'])
def stream_call_audio(room_id):
    """Stream audio file for a call (from S3 or local storage)."""
    if not CALL_HISTORY_AVAILABLE:
        return jsonify({"error": "Call history not available"}), 503
    
    try:
        logger.info(f"Requesting audio for room_id: '{room_id}'")
        call = get_call(room_id)
        logger.info(f"Call lookup result: {call}")
        if call:
            logger.info(f"Call audio_url: '{call.audio_url}'")
            
        if not call or not call.audio_url:
            logger.warning(f"Audio not found for room_id: {room_id}")
            return jsonify({"error": "Audio not found"}), 404
        
        if not call or not call.audio_url:
            logger.warning(f"Audio not found for room_id: {room_id}")
            return jsonify({"error": "Audio not found"}), 404
        
        # Helper to stream local file
        if os.path.exists(call.audio_url):
            from flask import send_file
            return send_file(call.audio_url, mimetype='audio/wav')

        # If it's an S3 URL, try to parse and stream
        if call.audio_url.startswith('s3://') or 's3.amazonaws.com' in call.audio_url or 's3.' in call.audio_url:
            try:
                import boto3
                from botocore.config import Config
                from urllib.parse import urlparse
                
                bucket = None
                key = None
                
                if call.audio_url.startswith('s3://'):
                    parts = call.audio_url[5:].split('/', 1)
                    bucket = parts[0]
                    key = parts[1] if len(parts) > 1 else ''
                else:
                    # Generic URL parsing
                    parsed = urlparse(call.audio_url)
                    # Handle virtual-hosted style: bucket.s3.region.amazonaws.com
                    if parsed.netloc.endswith('amazonaws.com') and parsed.netloc.startswith('s3'):
                        # path style? s3.region...
                         path_parts = parsed.path.lstrip('/').split('/', 1)
                         if len(path_parts) > 1:
                             bucket = path_parts[0]
                             key = path_parts[1]
                    else:
                        # Assume virtual host: bucket.s3...
                         bucket = parsed.netloc.split('.')[0]
                         key = parsed.path.lstrip('/')
                
                if not bucket or not key:
                    raise ValueError(f"Could not parse S3 URL: {call.audio_url}")

                # Get credentials from env or config
                aws_region = os.getenv("AWS_REGION") or config.get("integrations", {}).get("aws_region") or "us-east-1"
                aws_access_key = os.getenv("AWS_ACCESS_KEY_ID") or config.get("integrations", {}).get("aws_access_key_id")
                aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY") or config.get("integrations", {}).get("aws_secret_access_key")

                s3_client = boto3.client(
                    's3', 
                    config=Config(signature_version='s3v4'),
                    region_name=aws_region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret
                )
                logger.info(f"Attempting to fetch S3 object. Region: {aws_region}, Bucket: {bucket}, Key: {key}")
                try:
                    s3_response = s3_client.get_object(Bucket=bucket, Key=key)
                except s3_client.exceptions.NoSuchKey:
                    logger.warning(f"S3 Key not found: {key} in bucket {bucket}")
                    # Debug: List object in the bucket to see what's there
                    try:
                        objects = s3_client.list_objects_v2(Bucket=bucket, Prefix="calls/", MaxKeys=5)
                        if 'Contents' in objects:
                            keys = [obj['Key'] for obj in objects['Contents']]
                            logger.info(f"Available keys in calls/: {keys}")
                        else:
                            logger.info("No objects found in calls/ prefix")
                    except Exception as list_err:
                        logger.error(f"Failed to list objects: {list_err}")
                        
                    return jsonify({"error": f"Audio file not found in S3 (Key: {key})"}), 404
                except Exception as e:
                    # Generic boto3 error (permission, connection, etc)
                    logger.error(f"S3 Client Error: {e}")
                    raise e 
                
                def generate():
                    for chunk in s3_response['Body'].iter_chunks():
                        yield chunk
                
                return Response(
                    stream_with_context(generate()),
                    mimetype=s3_response.get('ContentType', 'audio/ogg'),
                    headers={"Content-Disposition": f"inline; filename={key.split('/')[-1] or 'recording.ogg'}"}
                )
            except Exception as e:
                # Check for 404 response from boto3 if not caught above
                if "NoSuchKey" in str(e) or "404" in str(e):
                     return jsonify({"error": "Audio file not found in S3"}), 404
                     
                logger.error(f"Error streaming from S3: {e}")
                
                # Fallback to redirect if streaming fails
                if call.audio_url.startswith('http'):
                     from flask import redirect
                     return redirect(call.audio_url)
                return jsonify({"error": f"Failed to stream from S3: {str(e)}"}), 500
        
        # If it's a HTTP URL but not seemingly S3 (or S3 fallback failed above), redirect
        elif call.audio_url.startswith('http'):
            from flask import redirect
            return redirect(call.audio_url)
        
        else:
            return jsonify({"error": "Audio file not accessible"}), 404
            
    except Exception as e:
        logger.error(f"Error streaming audio: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/calls/stats', methods=['GET'])
def call_stats():
    """Get call statistics."""
    if not CALL_HISTORY_AVAILABLE:
        return jsonify({"error": "Call history not available"}), 503
    
    try:
        call_history = get_call_history()
        return jsonify({
            "success": True,
            "stats": {
                "total": call_history.get_call_count(),
                "completed": call_history.get_call_count(status="completed"),
                "voicemail": call_history.get_call_count(status="voicemail"),
                "failed": call_history.get_call_count(status="failed"),
                "no_answer": call_history.get_call_count(status="no_answer"),
                "busy": call_history.get_call_count(status="busy")
            }
        })
    except Exception as e:
        logger.error(f"Error getting call stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/reset-voicemail-rows', methods=['POST'])
def reset_voicemail_rows():
    """Reset voicemail rows to Pending status, clearing data except phone and business name."""
    try:
        data = request.get_json() or {}
        sheet_id = data.get('sheet_id')
        
        # Use provided sheet_id or fall back to config/env
        if not sheet_id:
            config = load_config()
            sheet_id = config.get("integrations", {}).get("google_sheet_id") or os.getenv("GOOGLE_SHEET_ID")
        
        if not sheet_id:
            return jsonify({"success": False, "error": "No Google Sheet ID provided or configured"}), 400
        
        sheet_name = os.getenv("GOOGLE_SHEET_NAME", "la-orange-county-landscapers-full-template")
        
        # Get Google Sheets service
        service = get_google_sheets_service()
        
        # Read all data from sheet
        range_name = f"{sheet_name}!A:M"
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name,
        ).execute()
        
        values = result.get("values", [])
        
        if not values:
            return jsonify({"success": False, "error": "No data found in sheet"}), 404
        
        # Find Status column index
        headers = values[0]
        try:
            status_idx = headers.index("Status")
        except ValueError:
            return jsonify({"success": False, "error": "'Status' column not found in headers"}), 400
        
        # Find voicemail rows
        voicemail_rows = []
        for row_num, row in enumerate(values[1:], start=2):
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
            return jsonify({"success": True, "rows_reset": 0, "cells_updated": 0, "message": "No voicemail rows found"})
        
        # Build batch update - keep Phone (col 0) and Business name (col 9), clear rest, set Status to Pending
        batch_data = []
        for row_info in voicemail_rows:
            row_num = row_info["row_num"]
            phone = row_info["phone"]
            business = row_info["business"]
            
            # Build new row: 13 columns (A-M)
            new_row = [
                phone,     # A - Phone_number (keep)
                "",        # B - Name (clear)
                "Pending", # C - Status (set to Pending)
                "",        # D - Appointment Scheduled (clear)
                "",        # E - Appointment Time Scheduled (clear)
                "",        # F - Appointment Email (clear)
                "",        # G - Transcript (clear)
                "",        # H - Call Duration (clear)
                "",        # I - Last Called (clear)
                business,  # J - Business name (keep)
                "",        # K - Room Name (clear)
                "",        # L - Session ID (clear)
                "",        # M - Outcome Details (clear)
            ]
            
            range_to_update = f"{sheet_name}!A{row_num}:M{row_num}"
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
            spreadsheetId=sheet_id,
            body=body
        ).execute()
        
        cells_updated = result.get('totalUpdatedCells', 0)
        logger.info(f"Reset {len(voicemail_rows)} voicemail rows to Pending ({cells_updated} cells updated)")
        
        return jsonify({
            "success": True,
            "rows_reset": len(voicemail_rows),
            "cells_updated": cells_updated
        })
        
    except Exception as e:
        logger.error(f"Error resetting voicemail rows: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/upload-background-sound', methods=['POST'])
def upload_background_sound():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400
        
    if file and (file.filename.endswith('.mp3') or file.filename.endswith('.wav') or file.filename.endswith('.ogg')):
        filename = secure_filename(file.filename)
        # Ensure directory exists
        sounds_dir = os.path.join(app.static_folder, 'sounds')
        os.makedirs(sounds_dir, exist_ok=True)
        
        save_path = os.path.join(sounds_dir, filename)
        
        try:
            file.save(save_path)
            logger.info(f"Uploaded background sound: {filename}")
            return jsonify({
                "success": True, 
                "filename": filename,
                "path": f"static/sounds/{filename}",
                "url": f"sounds/{filename}"
            })
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {e}")
            return jsonify({"success": False, "error": f"Failed to save file: {e}"}), 500
            
    return jsonify({"success": False, "error": "Invalid file type. Allowed: mp3, wav, ogg"}), 400


def run_server(host=HOST, port=PORT, debug=False):
    """Run the Flask server."""
    logger.info(f"Starting web server on http://{host}:{port}")
    logger.info(f"Access the configuration interface at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)
