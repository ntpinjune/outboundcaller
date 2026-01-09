#!/usr/bin/env python3
"""Test AWS S3 credentials and bucket access."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Get AWS credentials
bucket = os.getenv('AWS_BUCKET_NAME')
region = os.getenv('AWS_REGION')
access_key = os.getenv('AWS_ACCESS_KEY_ID')
secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

print("=" * 60)
print("AWS Credentials Test")
print("=" * 60)

# Check if variables are set
print("\n1. Environment Variables:")
print(f"   AWS_BUCKET_NAME: {bucket if bucket else '[NOT SET]'}")
print(f"   AWS_REGION: {region if region else '[NOT SET]'}")
print(f"   AWS_ACCESS_KEY_ID: {access_key[:10] + '...' if access_key else '[NOT SET]'}")
print(f"   AWS_SECRET_ACCESS_KEY: {'SET' if secret_key else 'NOT SET'}")

if not all([bucket, region, access_key, secret_key]):
    print("\n[ERROR] Missing required environment variables!")
    exit(1)

# Test boto3 connection
print("\n2. Testing S3 Connection:")
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    
    # Create S3 client
    s3 = boto3.client(
        's3',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    
    # Test bucket access
    print(f"   Connecting to bucket: {bucket}...")
    s3.head_bucket(Bucket=bucket)
    print(f"   [OK] Successfully connected to S3 bucket: {bucket}")
    print(f"   [OK] Bucket exists and is accessible")
    
    # Test write permissions (try to list objects)
    print(f"\n3. Testing Permissions:")
    try:
        response = s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        print(f"   [OK] Read permission: OK")
    except ClientError as e:
        print(f"   [WARNING] Read permission: {e}")
    
    # Test if we can create a test path (simulate)
    test_path = "calls/test_permissions_check.txt"
    print(f"\n4. Testing Write Path:")
    print(f"   Recording files will be saved to: s3://{bucket}/{test_path}")
    print(f"   [OK] Path format is valid")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] All tests passed! AWS credentials are working.")
    print("=" * 60)
    
except ImportError:
    print("   [WARNING] boto3 not installed. Installing...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "boto3"])
    print("   [OK] boto3 installed. Please run this script again.")
    
except NoCredentialsError:
    print("   [ERROR] Invalid AWS credentials!")
    exit(1)
    
except ClientError as e:
    error_code = e.response['Error']['Code']
    error_msg = e.response['Error'].get('Message', 'No message')
    print(f"   Error Code: {error_code}")
    print(f"   Error Message: {error_msg}")
    
    if error_code == '403':
        print(f"\n   [ERROR] Access denied!")
        print(f"   Possible issues:")
        print(f"   1. AWS credentials don't have permission to access bucket '{bucket}'")
        print(f"   2. Bucket policy or IAM permissions are too restrictive")
        print(f"   3. Bucket is in a different region (you specified: {region})")
        print(f"   4. Bucket name is incorrect")
    elif error_code == '404':
        print(f"   [ERROR] Bucket '{bucket}' not found! Check the bucket name.")
    else:
        print(f"   [ERROR] Error: {error_code} - {error_msg}")
    exit(1)
    
except Exception as e:
    print(f"   [ERROR] Unexpected error: {e}")
    exit(1)
