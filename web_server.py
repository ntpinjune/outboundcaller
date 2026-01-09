"""
Web Server for Outbound Caller Agent Configuration

Provides a REST API and web interface for configuring the agent without code changes.
"""

import os
import json
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from typing import Dict, Any, Optional
import subprocess
import threading
from datetime import datetime
import base64
import hmac
import hashlib
import requests

from config_manager import load_config, save_config, get_config_value, load_system_prompt

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web-server")

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Configuration
PORT = int(os.getenv("WEB_SERVER_PORT", "5000"))
HOST = os.getenv("WEB_SERVER_HOST", "127.0.0.1")


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
            return jsonify({
                "success": True,
                "message": "Configuration updated successfully"
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
    """Get current system prompt."""
    try:
        prompt = load_system_prompt()
        return jsonify({
            "success": True,
            "prompt": prompt
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
            return jsonify({
                "success": True,
                "message": "System prompt updated successfully"
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


def run_server(host=HOST, port=PORT, debug=False):
    """Run the Flask server."""
    logger.info(f"🚀 Starting web server on http://{host}:{port}")
    logger.info(f"📝 Access the configuration interface at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)
