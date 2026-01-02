#!/usr/bin/env python3
"""Test if agent can receive jobs and what might be wrong."""

import os
import json
import requests
import base64
import hmac
import hashlib
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
print("Agent Connection Diagnostic")
print("=" * 60)
print()

# Check credentials
print("1. Checking credentials...")
if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
    print("   ❌ Missing API credentials!")
    exit(1)
print(f"   ✅ API Key: {LIVEKIT_API_KEY[:10]}...")
print(f"   ✅ API Secret: ***{LIVEKIT_API_SECRET[-5:]}")
print()

# Generate JWT
print("2. Generating JWT token...")
jwt = generate_jwt()
print(f"   ✅ JWT generated: {jwt[:50]}...")
print()

# Test API call
print("3. Testing job dispatch...")
url = f"{LIVEKIT_URL}/twirp/livekit.AgentService/CreateJob"
headers = {
    "Authorization": f"Bearer {jwt}",
    "Content-Type": "application/json"
}
payload = {
    "job": {
        "agent_name": AGENT_NAME,
        "room_name": "",
        "metadata": json.dumps({
            "phone_number": "+12095539289",
            "name": "Test User",
            "appointment_time": "",
            "row_id": "test-1"
        })
    }
}

print(f"   URL: {url}")
print(f"   Agent Name: {AGENT_NAME}")
print(f"   Payload: {json.dumps(payload, indent=2)}")
print()

try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {response.text}")
    print()
    
    if response.status_code == 200:
        print("   ✅ Job dispatched successfully!")
        print()
        print("=" * 60)
        print("NEXT STEPS:")
        print("=" * 60)
        print("1. Go to LiveKit Cloud Dashboard")
        print("2. Navigate to: Agents → CA_ERnckSYLUAYN → Logs")
        print("3. Look for these messages:")
        print("   - 'connecting to room' → Agent received job ✅")
        print("   - 'create_sip_participant' → Starting to dial ✅")
        print("   - 'participant joined' → Call connected ✅")
        print()
        print("If you DON'T see 'connecting to room':")
        print("  - Agent might not be running")
        print("  - Agent name might not match")
        print("  - Check agent status in dashboard")
        print()
        print("If you see 'connecting to room' but no dialing:")
        print("  - Check SIP_OUTBOUND_TRUNK_ID in environment variables")
        print("  - Verify SIP trunk is active")
        print("  - Check for API key errors (Deepgram, Cartesia, etc.)")
    else:
        print(f"   ❌ Failed with status {response.status_code}")
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()


