import asyncio
import os
import json
import requests
import boto3
import time
from datetime import datetime
from dotenv import load_dotenv

# Load env
load_dotenv(".env.local")

SERVER_URL = "http://localhost:5000"
BUCKET_NAME = os.getenv("AWS_BUCKET_NAME", "colcallerd")

def dispatch_fake_call():
    """Dispatch a call via the local web server API."""
    phone = "+15550009999"  # Fake number
    payload = {
        "phone_number": phone,
        "name": "Recording Test",
        "appointment_time": "Tomorrow 2pm",
        "business_name": "Test Business"
    }
    
    print(f"Dispatching fake call to {phone}...")
    try:
        res = requests.post(f"{SERVER_URL}/api/calls/dispatch", json=payload)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ Dispatch success! Job ID: {data.get('job_id')}")
            return phone
        else:
            print(f"❌ Dispatch failed: {res.text}")
            return None
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")
        return None

def check_s3_for_file(phone_number):
    """Poll S3 for the expected recording file."""
    s3 = boto3.client('s3', 
                      aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                      aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                      region_name=os.getenv("AWS_REGION", "us-east-2"))
    
    # Expected filename pattern: calls/{phone}_{timestamp}.ogg
    # Since we don't know the exact timestamp, we'll look for recent files matching the phone number
    phone_clean = phone_number.replace("+", "")
    prefix = f"calls/{phone_clean}_"
    
    print(f"Polling S3 bucket '{BUCKET_NAME}' for file starting with: {prefix}...")
    
    start_time = time.time()
    timeout = 120 # Wait up to 2 minutes (agent needs to connect, record, upload)
    
    while time.time() - start_time < timeout:
        try:
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
            if 'Contents' in response:
                # Find the most recent file
                files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
                latest_file = files[0]
                
                # Check if it's new (created in the last 2 minutes)
                # Note: S3 datetime is timezone aware
                elapsed_since_upload = (datetime.now(latest_file['LastModified'].tzinfo) - latest_file['LastModified']).total_seconds()
                
                if elapsed_since_upload < 180: # Created recently
                    print(f"✅ Found recording: {latest_file['Key']} ({latest_file['Size']} bytes)")
                    return True
                
            time.sleep(5)
            print(".", end="", flush=True)
        except Exception as e:
            print(f"\nError checking S3: {e}")
            time.sleep(5)
            
    print("\n❌ Timed out waiting for recording file.")
    return False

if __name__ == "__main__":
    print("=== STARTING FAKE CALL RECORDING TEST ===")
    phone = dispatch_fake_call()
    if phone:
        print("Waiting for agent to process call and upload recording (this may take 30-60s)...")
        success = check_s3_for_file(phone)
        if success:
            print("\n🎉 SUCCESS: Fake call was dispatched and recording matches expected format!")
        else:
            print("\nFAILED: Recording was not found in S3.")
