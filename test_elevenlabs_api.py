#!/usr/bin/env python3
"""Test script to verify ElevenLabs API key and voice ID."""

import os
import sys
from dotenv import load_dotenv
import requests

load_dotenv('.env.local')

API_KEY = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "4tRn1lSkEn13EVTuqb0g")

print("=" * 60)
print("ElevenLabs API Test")
print("=" * 60)
print(f"API Key: {API_KEY[:20]}...{API_KEY[-10:] if API_KEY else 'NOT SET'}")
print(f"Voice ID: {VOICE_ID}")
print()

if not API_KEY:
    print("❌ ERROR: ELEVEN_API_KEY not found in .env.local")
    sys.exit(1)

# Test 1: Verify API key by getting user info
print("Test 1: Verifying API key...")
try:
    headers = {"xi-api-key": API_KEY}
    response = requests.get("https://api.elevenlabs.io/v1/user", headers=headers)
    if response.status_code == 200:
        user_data = response.json()
        print(f"✅ API Key is valid")
        print(f"   Subscription: {user_data.get('subscription', {}).get('tier', 'Unknown')}")
        print(f"   Character count: {user_data.get('subscription', {}).get('character_count', 0)}")
        print(f"   Character limit: {user_data.get('subscription', {}).get('character_limit', 0)}")
    else:
        print(f"❌ API Key validation failed: {response.status_code}")
        print(f"   Response: {response.text}")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error validating API key: {e}")
    sys.exit(1)

print()

# Test 2: List available voices
print("Test 2: Listing available voices...")
try:
    headers = {"xi-api-key": API_KEY}
    response = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers)
    if response.status_code == 200:
        voices = response.json().get("voices", [])
        print(f"✅ Found {len(voices)} voices in your account")
        
        # Check if our voice ID exists
        voice_found = False
        for voice in voices:
            if voice.get("voice_id") == VOICE_ID:
                voice_found = True
                print(f"✅ Voice ID {VOICE_ID} found!")
                print(f"   Name: {voice.get('name')}")
                print(f"   Category: {voice.get('category')}")
                break
        
        if not voice_found:
            print(f"❌ Voice ID {VOICE_ID} NOT found in your account!")
            print("\nAvailable voice IDs:")
            for voice in voices[:10]:  # Show first 10
                print(f"   - {voice.get('voice_id')}: {voice.get('name')}")
            if len(voices) > 10:
                print(f"   ... and {len(voices) - 10} more")
    else:
        print(f"❌ Failed to list voices: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Error listing voices: {e}")

print()

# Test 3: Test text-to-speech generation
print("Test 3: Testing text-to-speech generation...")
try:
    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "text": "Hello, this is a test.",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        headers=headers,
        json=data
    )
    if response.status_code == 200:
        print(f"✅ Text-to-speech generation successful!")
        print(f"   Audio size: {len(response.content)} bytes")
    else:
        print(f"❌ Text-to-speech failed: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Error testing text-to-speech: {e}")

print()
print("=" * 60)
print("Test Complete")
print("=" * 60)

