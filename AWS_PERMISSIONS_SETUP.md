# AWS S3 Permissions Setup Guide

## Issue
Your AWS access key is valid, but the IAM user doesn't have permission to access the S3 bucket `colcallerd`.

## Solution: Add S3 Permissions

### Step 1: Check Current Permissions
1. In the AWS IAM Console, click on the **"Permissions"** tab (next to "Security credentials")
2. Check what policies are currently attached to the user `hihihi`
3. If there are no S3-related policies, continue to Step 2

### Step 2: Attach S3 Policy

You have two options:

#### Option A: Use AWS Managed Policy (Easiest)
1. In the **Permissions** tab, click **"Add permissions"** → **"Attach policies directly"**
2. Search for: `AmazonS3FullAccess` or `AmazonS3ReadWriteAccess`
3. Select it and click **"Add permissions"**

**Note:** This gives access to ALL S3 buckets. For better security, use Option B.

#### Option B: Create Custom Policy (Recommended)
1. Go to **IAM** → **Policies** → **"Create policy"**
2. Click **"JSON"** tab
3. Paste this policy (already saved in `s3_policy_example.json`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:HeadBucket",
        "s3:GetBucketLocation",
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::colcallerd"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::colcallerd/*"
    }
  ]
}
```

4. Click **"Next"** → Name it: `S3CallRecordingAccess`
5. Click **"Create policy"**
6. Go back to your user `hihihi` → **Permissions** tab
7. Click **"Add permissions"** → **"Attach policies directly"**
8. Search for `S3CallRecordingAccess` and attach it

### Step 3: Verify Permissions
After adding permissions, run the test again:

```powershell
.\venv\Scripts\activate
python test_aws_credentials.py
```

You should see: `[SUCCESS] All tests passed! AWS credentials are working.`

## What These Permissions Do

- **s3:HeadBucket** - Check if bucket exists (required for LiveKit egress)
- **s3:GetBucketLocation** - Get bucket region
- **s3:ListBucket** - List objects in bucket (for testing)
- **s3:PutObject** - Upload recording files (required)
- **s3:GetObject** - Read files (optional, for testing)
- **s3:DeleteObject** - Delete files (optional)

## Troubleshooting

### Still Getting 403 Error?
1. **Wait a few minutes** - IAM permissions can take 1-2 minutes to propagate
2. **Check bucket name** - Make sure it's exactly `colcallerd` (case-sensitive)
3. **Check bucket region** - Verify the bucket is in `us-east-2`
4. **Check bucket policy** - The bucket itself might have a policy blocking access

### Bucket Doesn't Exist?
If you get a 404 error, create the bucket:
1. Go to **S3 Console** → **"Create bucket"**
2. Name: `colcallerd`
3. Region: `us-east-2`
4. Click **"Create bucket"**

## Security Note

The custom policy (Option B) only gives access to the `colcallerd` bucket, which is more secure than giving access to all S3 buckets.
