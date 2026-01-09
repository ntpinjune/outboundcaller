#!/usr/bin/env python3
"""Check if call recordings exist in S3 bucket."""

import os
import boto3
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv('.env.local')

print("=" * 70)
print("S3 Call Recordings Check")
print("=" * 70)

# Get AWS credentials
bucket = os.getenv("AWS_BUCKET_NAME")
region = os.getenv("AWS_REGION", "us-east-1")
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

if not all([bucket, access_key, secret_key]):
    print("\n[ERROR] AWS credentials not configured!")
    print("Make sure AWS_BUCKET_NAME, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY are set in .env.local")
    exit(1)

print(f"\n1. Connecting to S3 bucket: {bucket}")
print("-" * 70)

try:
    s3 = boto3.client(
        's3',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    
    # Check if bucket exists
    s3.head_bucket(Bucket=bucket)
    print(f"   [OK] Connected to bucket: {bucket}")
    
except Exception as e:
    print(f"   [ERROR] Failed to connect: {e}")
    exit(1)

# List recordings
print(f"\n2. Checking for recordings in 'calls/' folder:")
print("-" * 70)

try:
    # List objects in the calls/ prefix
    response = s3.list_objects_v2(Bucket=bucket, Prefix="calls/")
    
    if 'Contents' not in response:
        print("   [INFO] No recordings found in calls/ folder")
        print("   This could mean:")
        print("     - No calls have been made yet")
        print("     - Recordings haven't finished uploading")
        print("     - Recording failed to start")
        print("\n   To verify recording is working:")
        print("     1. Make a test call")
        print("     2. Wait 1-2 minutes after the call ends")
        print("     3. Run this script again")
    else:
        recordings = response['Contents']
        print(f"   [OK] Found {len(recordings)} recording(s):\n")
        
        # Sort by last modified (newest first)
        recordings.sort(key=lambda x: x['LastModified'], reverse=True)
        
        for i, obj in enumerate(recordings[:20], 1):  # Show last 20
            filename = obj['Key']
            size = obj['Size']
            modified = obj['LastModified']
            size_mb = size / (1024 * 1024)
            
            # Extract phone number and timestamp from filename
            # Format: calls/{phone}_{timestamp}.ogg
            base_name = filename.replace("calls/", "").replace(".ogg", "")
            parts = base_name.split("_")
            
            if len(parts) >= 2:
                phone = parts[0]
                timestamp = "_".join(parts[1:])
                print(f"   {i}. {filename}")
                print(f"      Phone: {phone}")
                print(f"      Date: {timestamp}")
                print(f"      Size: {size_mb:.2f} MB")
                print(f"      Uploaded: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"   {i}. {filename}")
                print(f"      Size: {size_mb:.2f} MB")
                print(f"      Uploaded: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
        
        if len(recordings) > 20:
            print(f"   ... and {len(recordings) - 20} more recording(s)")
        
        # Show recent recordings (last 24 hours)
        if recordings:
            now = datetime.now(recordings[0]['LastModified'].tzinfo)
            recent = [r for r in recordings if (now - r['LastModified']).total_seconds() < 86400]
        
        if recent:
            print(f"\n   [INFO] {len(recent)} recording(s) from the last 24 hours")
        
except Exception as e:
    print(f"   [ERROR] Failed to list recordings: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 70)
print("How to verify recording is working:")
print("=" * 70)
print("1. Check agent logs for:")
print("   - 'Starting S3 recording: s3://...'")
print("   - 'Recording started successfully. Egress ID: ...'")
print("\n2. After a call ends, wait 1-2 minutes for upload")
print("\n3. Run this script again to see new recordings")
print("\n4. Or check your S3 bucket directly:")
print(f"   https://s3.console.aws.amazon.com/s3/buckets/{bucket}?prefix=calls/")
