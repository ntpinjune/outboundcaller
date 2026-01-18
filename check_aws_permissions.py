import os
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-2')
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')

print(f"--- Checking AWS Configuration ---")
print(f"Bucket: {AWS_BUCKET_NAME}")
print(f"Region: {AWS_REGION}")
print(f"Access Key: {'*' * 16 + AWS_ACCESS_KEY_ID[-4:] if AWS_ACCESS_KEY_ID else 'MISSING'}")

if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BUCKET_NAME]):
    print("❌ Critical: Missing AWS credentials in .env.local")
    exit(1)

try:
    s3 = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

    # 1. Check if we can list the bucket (tests Read/List permissions)
    print(f"\n[1/2] Testing Read Access (List Objects)...")
    s3.list_objects_v2(Bucket=AWS_BUCKET_NAME, MaxKeys=1)
    print("✅ Read/List Access: OK")

    # 2. Check if we can write to the bucket (tests PutObject permissions)
    print(f"\n[2/2] Testing Write Access (Upload Test File)...")
    test_filename = "permissions_check.txt"
    s3.put_object(Bucket=AWS_BUCKET_NAME, Key=test_filename, Body=b"Write access test successful!")
    print(f"✅ Write Access: OK (Uploaded {test_filename})")
    
    # Cleanup
    s3.delete_object(Bucket=AWS_BUCKET_NAME, Key=test_filename)
    print("✅ Cleanup: OK")
    
    print("\n🎉 AWS S3 Permissions are correctly configured!")

except Exception as e:
    print(f"\n❌ AWS Permission Check Failed:")
    print(str(e))
    print("\nTroubleshooting:")
    if "InvalidAccessKeyId" in str(e):
        print("- The Access Key ID is incorrect or invalid.")
    elif "SignatureDoesNotMatch" in str(e):
        print("- The Secret Access Key is incorrect.")
    elif "NoSuchBucket" in str(e):
        print(f"- The bucket '{AWS_BUCKET_NAME}' does not exist in region '{AWS_REGION}'.")
    elif "AccessDenied" in str(e):
        print("- The user does not have permission (s3:ListBucket or s3:PutObject) for this bucket.")
