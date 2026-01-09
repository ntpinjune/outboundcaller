#!/usr/bin/env python3
"""Quick verification of agent setup."""

import os
from dotenv import load_dotenv

load_dotenv('.env.local')

print("=" * 70)
print("Agent Setup Verification")
print("=" * 70)

required = {
    "LIVEKIT_URL": os.getenv("LIVEKIT_URL"),
    "LIVEKIT_API_KEY": os.getenv("LIVEKIT_API_KEY"),
    "LIVEKIT_API_SECRET": os.getenv("LIVEKIT_API_SECRET"),
    "SIP_OUTBOUND_TRUNK_ID": os.getenv("SIP_OUTBOUND_TRUNK_ID"),
    "ELEVEN_API_KEY": os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY"),
}

optional = {
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "GOOGLE_SHEET_ID": os.getenv("GOOGLE_SHEET_ID"),
    "AWS_BUCKET_NAME": os.getenv("AWS_BUCKET_NAME"),
}

print("\n1. Required Environment Variables:")
print("-" * 70)
all_required = True
for key, value in required.items():
    status = "[OK]" if value else "[MISSING]"
    if not value:
        all_required = False
    print(f"   {status} {key}")

print("\n2. Optional Environment Variables:")
print("-" * 70)
for key, value in optional.items():
    status = "[SET]" if value else "[NOT SET]"
    print(f"   {status} {key}")

print("\n3. Setup Status:")
print("-" * 70)
if all_required:
    print("   [OK] All required variables are set")
    print("   [OK] Agent should be ready to run")
else:
    print("   [ERROR] Missing required variables!")
    print("   Please set the missing variables in .env.local")

print("\n4. Known Issues:")
print("-" * 70)
print("   - Check that record=True is removed from session.start()")
print("   - Recording is handled by egress API, not session.start()")

print("\n" + "=" * 70)
if all_required:
    print("[SUCCESS] Agent setup looks good!")
    print("Start your agent with: .\\venv\\Scripts\\python.exe agent.py dev")
else:
    print("[ERROR] Please fix missing environment variables")
print("=" * 70)
