#!/usr/bin/env python3
"""Quick test script to verify LiveKit API connection."""

import os
import json
import base64
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "https://cold-caller-6vmkvmbr.livekit.cloud")
LIVEKIT_URL = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
AGENT_NAME = "outbound-caller-dev"

def generate_jwt():
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
    
    def base64url_encode(data):
        json_str = json.dumps(data, separators=(',', ':'))
        encoded = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')
        return encoded.rstrip('=')
    
    encoded_header = base64url_encode(header)
    encoded_payload = base64url_encode(payload)
    message = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(
        LIVEKIT_API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

print("=" * 60)
print("LiveKit API Test")
print("=" * 60)
print(f"URL: {LIVEKIT_URL}")
print(f"API Key: {LIVEKIT_API_KEY[:10]}..." if LIVEKIT_API_KEY else "❌ MISSING")
print(f"API Secret: {'***' + LIVEKIT_API_SECRET[-5:] if LIVEKIT_API_SECRET else '❌ MISSING'}")
print(f"Agent Name: {AGENT_NAME}")
print()

if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
    print("❌ Missing API credentials!")
    exit(1)

# Generate JWT
jwt = generate_jwt()
print(f"JWT generated: {jwt[:50]}...")
print()

# Test API call
url = f"{LIVEKIT_URL}/twirp/livekit.AgentService/CreateJob"
headers = {
    "Authorization": f"Bearer {jwt}",
    "Content-Type": "application/json"
}
payload = {
    "job": {
        "agent_name": AGENT_NAME,
        "room_name": "",
        "metadata": json.dumps({"phone_number": "+12095539289", "name": "Test", "row_id": "1"})
    }
}

print(f"Making request to: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print()

try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print()
    print(f"Response Text:")
    print(response.text)
    print()
    
    if response.status_code == 200:
        try:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"Job ID: {result.get('job', {}).get('id', 'unknown')}")
        except:
            print("⚠️  Status 200 but response is not JSON")
    else:
        print(f"❌ FAILED with status {response.status_code}")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()


