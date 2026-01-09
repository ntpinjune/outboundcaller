#!/usr/bin/env python3
"""Test ElevenLabs TTS API to diagnose the 'no audio frames' error."""

import os
import requests
from dotenv import load_dotenv

load_dotenv('.env.local')

print("=" * 70)
print("ElevenLabs TTS API Diagnostic Test")
print("=" * 70)

# Get credentials
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "6AUOG2nbfr0yFEeI0784")

print("\n1. Checking Environment Variables:")
print("-" * 70)
print(f"   ELEVEN_API_KEY: {'SET' if ELEVEN_API_KEY else '[NOT SET]'}")
if ELEVEN_API_KEY:
    print(f"   ELEVEN_API_KEY (first 10 chars): {ELEVEN_API_KEY[:10]}...")
print(f"   ELEVENLABS_VOICE_ID: {ELEVENLABS_VOICE_ID}")

if not ELEVEN_API_KEY:
    print("\n[ERROR] ELEVEN_API_KEY not found!")
    exit(1)

# Test 1: Check user info
print("\n2. Testing ElevenLabs API Connection:")
print("-" * 70)
try:
    headers = {"xi-api-key": ELEVEN_API_KEY}
    response = requests.get("https://api.elevenlabs.io/v1/user", headers=headers, timeout=10)
    
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 200:
        user_data = response.json()
        print(f"   [OK] API connection successful")
        print(f"   Subscription: {user_data.get('subscription', {}).get('tier', 'Unknown')}")
        print(f"   Character Count: {user_data.get('subscription', {}).get('character_count', 0)}")
        print(f"   Character Limit: {user_data.get('subscription', {}).get('character_limit', 0)}")
    elif response.status_code == 401:
        print(f"   [ERROR] Invalid API key! Check your ELEVEN_API_KEY")
        print(f"   Response: {response.text[:200]}")
        exit(1)
    else:
        print(f"   [ERROR] API error: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        exit(1)
        
except Exception as e:
    print(f"   [ERROR] Failed to connect to ElevenLabs API: {e}")
    exit(1)

# Test 2: Check voice exists
print("\n3. Testing Voice ID:")
print("-" * 70)
try:
    headers = {"xi-api-key": ELEVEN_API_KEY}
    response = requests.get(f"https://api.elevenlabs.io/v1/voices/{ELEVENLABS_VOICE_ID}", headers=headers, timeout=10)
    
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 200:
        voice_data = response.json()
        print(f"   [OK] Voice found: {voice_data.get('name', 'Unknown')}")
        print(f"   Voice ID: {voice_data.get('voice_id', 'Unknown')}")
    elif response.status_code == 404:
        print(f"   [ERROR] Voice ID '{ELEVENLABS_VOICE_ID}' not found!")
        print(f"   Make sure the voice exists in your account at: https://elevenlabs.io/app/voices")
        exit(1)
    else:
        print(f"   [ERROR] Failed to get voice: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        exit(1)
        
except Exception as e:
    print(f"   [ERROR] Failed to check voice: {e}")
    exit(1)

# Test 3: Try text-to-speech API call
print("\n4. Testing Text-to-Speech API:")
print("-" * 70)
try:
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json"
    }
    
    data = {
        "text": "Hello?",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "speed": 1.3
        }
    }
    
    # Try streaming endpoint
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"
    print(f"   Testing streaming endpoint: {url}")
    
    response = requests.post(url, json=data, headers=headers, timeout=10, stream=True)
    
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 200:
        # Try to read some audio data
        audio_data = b""
        for chunk in response.iter_content(chunk_size=1024):
            audio_data += chunk
            if len(audio_data) > 1000:  # Read at least 1KB
                break
        
        if len(audio_data) > 0:
            print(f"   [OK] Successfully received {len(audio_data)} bytes of audio data")
            print(f"   [OK] TTS API is working correctly!")
        else:
            print(f"   [WARNING] Response OK but no audio data received")
    elif response.status_code == 401:
        print(f"   [ERROR] Invalid API key!")
        exit(1)
    elif response.status_code == 402:
        print(f"   [ERROR] Payment required or quota exceeded!")
        print(f"   Check your ElevenLabs subscription at: https://elevenlabs.io/app/settings")
        exit(1)
    elif response.status_code == 429:
        print(f"   [ERROR] Rate limit exceeded!")
        print(f"   Wait a few minutes and try again")
        exit(1)
    else:
        print(f"   [ERROR] TTS API error: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        exit(1)
        
except Exception as e:
    print(f"   [ERROR] Failed to test TTS: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 70)
print("[SUCCESS] All ElevenLabs API tests passed!")
print("=" * 70)
print("\nIf the agent still fails, the issue might be:")
print("  1. Network connectivity during the call")
print("  2. WebSocket streaming vs HTTP API differences")
print("  3. LiveKit plugin configuration issue")
print("\nTry restarting the agent and making another call.")
