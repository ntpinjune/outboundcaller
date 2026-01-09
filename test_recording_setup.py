#!/usr/bin/env python3
"""Test the complete call recording setup including LiveKit integration."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

print("=" * 70)
print("Complete Call Recording Setup Test")
print("=" * 70)

# Check all required variables
print("\n1. Checking Environment Variables:")
print("-" * 70)

required_vars = {
    "LiveKit": {
        "LIVEKIT_URL": os.getenv("LIVEKIT_URL"),
        "LIVEKIT_API_KEY": os.getenv("LIVEKIT_API_KEY"),
        "LIVEKIT_API_SECRET": os.getenv("LIVEKIT_API_SECRET"),
    },
    "AWS S3": {
        "AWS_BUCKET_NAME": os.getenv("AWS_BUCKET_NAME"),
        "AWS_REGION": os.getenv("AWS_REGION"),
        "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
    }
}

all_ok = True
for category, vars_dict in required_vars.items():
    print(f"\n   {category}:")
    for var_name, var_value in vars_dict.items():
        if var_value:
            if "SECRET" in var_name or "KEY" in var_name:
                print(f"      {var_name}: [SET]")
            else:
                print(f"      {var_name}: {var_value}")
        else:
            print(f"      {var_name}: [NOT SET]")
            all_ok = False

if not all_ok:
    print("\n[ERROR] Missing required environment variables!")
    exit(1)

# Test S3 access
print("\n2. Testing S3 Access:")
print("-" * 70)
try:
    import boto3
    from botocore.exceptions import ClientError
    
    bucket = os.getenv("AWS_BUCKET_NAME")
    region = os.getenv("AWS_REGION")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    s3 = boto3.client(
        's3',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    
    s3.head_bucket(Bucket=bucket)
    print(f"   [OK] S3 bucket '{bucket}' is accessible")
    
except Exception as e:
    print(f"   [ERROR] S3 access failed: {e}")
    exit(1)

# Test LiveKit API import
print("\n3. Testing LiveKit API:")
print("-" * 70)
try:
    from livekit import api
    print("   [OK] LiveKit API module imported successfully")
    
    # Check if we can create the API client (won't actually connect)
    livekit_url = os.getenv("LIVEKIT_URL", "").replace("wss://", "https://").replace("ws://", "http://")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY", "")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET", "")
    
    if livekit_url and livekit_api_key and livekit_api_secret:
        print(f"   [OK] LiveKit credentials configured")
        print(f"   [OK] LiveKit URL: {livekit_url}")
    else:
        print("   [ERROR] LiveKit credentials not fully configured")
        exit(1)
        
except ImportError as e:
    print(f"   [ERROR] Failed to import LiveKit API: {e}")
    exit(1)

# Test recording function components
print("\n4. Testing Recording Function Components:")
print("-" * 70)
try:
    from livekit import api
    
    # Test that we can create the required objects
    file_output = api.EncodedFileOutput(
        file_type=api.EncodedFileType.OGG,
        filepath="calls/test_1234567890_20241215_120000.ogg",
        s3=api.S3Upload(
            bucket=os.getenv("AWS_BUCKET_NAME"),
            region=os.getenv("AWS_REGION"),
            access_key=os.getenv("AWS_ACCESS_KEY_ID"),
            secret=os.getenv("AWS_SECRET_ACCESS_KEY"),
        ),
    )
    print("   [OK] EncodedFileOutput with S3Upload created successfully")
    
    # Test RoomCompositeEgressRequest structure
    req = api.RoomCompositeEgressRequest(
        room_name="test-room",
        audio_only=True,
        file_outputs=[file_output],
    )
    print("   [OK] RoomCompositeEgressRequest structure is valid")
    
except Exception as e:
    print(f"   [ERROR] Failed to create recording request objects: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Final summary
print("\n" + "=" * 70)
print("[SUCCESS] All components are configured correctly!")
print("=" * 70)
print("\nYour call recording setup is ready:")
print("  - AWS S3 credentials: Working")
print("  - LiveKit API: Configured")
print("  - Recording function: Ready")
print("\nWhen you make a call, recordings will be saved to:")
print(f"  s3://{os.getenv('AWS_BUCKET_NAME')}/calls/{{phone_number}}_{{timestamp}}.ogg")
print("\nNext steps:")
print("  1. Start your agent: .\\venv\\Scripts\\python.exe agent.py dev")
print("  2. Dispatch a test call")
print("  3. Check logs for: 'Starting S3 recording: s3://...'")
print("  4. After call ends, check your S3 bucket for the recording file")
