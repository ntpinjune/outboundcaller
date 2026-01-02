# Google Calendar Integration Setup Guide

This guide will help you set up Google Calendar integration for the outbound caller agent.

## Prerequisites

- A Google account
- Access to Google Cloud Console
- The agent codebase with `google_calendar.py` and required dependencies installed

## Step-by-Step Setup

### Step 1: Enable Google Calendar API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** > **Library**
4. Search for "Google Calendar API"
5. Click on it and press **Enable**

### Step 2: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. If prompted, configure the OAuth consent screen first:
   - Choose **External** (unless you have a Google Workspace account)
   - Fill in the required fields (App name, User support email, etc.)
   - Add your email to test users
   - Click **Save and Continue** through the steps
4. Back in Credentials, select **Application type**: **Desktop app**
5. Give it a name (e.g., "Outbound Caller Agent")
6. Click **Create**
7. Download the JSON file
8. Save it as `credentials.json` in your project root directory

### Step 3: Test Authentication

Run the test script to authenticate:

```bash
python test_google_auth.py
```

This will:
- Check if `credentials.json` exists
- Open a browser window for Google sign-in
- Save your credentials to `token.json`
- Verify the authentication worked

**Note:** The first time you run this, a browser window will open asking you to:
1. Sign in to your Google account
2. Grant permission to access your Google Calendar
3. You may see a warning about the app not being verified - click "Advanced" > "Go to [App Name] (unsafe)" to proceed

### Step 4: Verify It's Working

After authentication, the `token.json` file will be created automatically. This file stores your access and refresh tokens.

**Test the integration:**

```bash
python -c "from google_calendar import GoogleCalendar; import asyncio; cal = GoogleCalendar(); asyncio.run(cal.create_meet_event('your-email@example.com', __import__('datetime').datetime.now() + __import__('datetime').timedelta(hours=1), 'Test Meeting'))"
```

Or simply run the agent and try scheduling a meeting - if authentication works, it should create calendar events automatically.

## Files Involved

- **`credentials.json`** - OAuth 2.0 client credentials (download from Google Cloud Console)
- **`token.json`** - Your access/refresh tokens (created automatically after first auth)
- **`google_calendar.py`** - The integration code

## Troubleshooting

### Error: "credentials.json not found"
- Make sure you downloaded the OAuth 2.0 credentials from Google Cloud Console
- Save it as `credentials.json` in the project root directory

### Error: "OAuth flow failed"
- Check your internet connection
- Make sure the Calendar API is enabled in Google Cloud Console
- Verify your OAuth consent screen is configured
- Try deleting `token.json` and running the test script again

### Error: "Token expired" or "Invalid credentials"
- The `token.json` file may be expired or invalid
- Delete `token.json` and run `python test_google_auth.py` again to re-authenticate
- The refresh token should automatically renew expired access tokens

### Browser doesn't open for authentication
- Check the terminal for a URL to visit manually
- Make sure you're running the script from the terminal (not in a headless environment)

### "App not verified" warning
- This is normal for personal/testing projects
- Click "Advanced" > "Go to [App Name] (unsafe)" to proceed
- For production use, you'll need to verify your app through Google

## What the Integration Does

Once set up, the agent can:
- ✅ Check calendar availability for specific times
- ✅ Create Google Calendar events with Google Meet links
- ✅ Send calendar invites to customers via email
- ✅ Automatically schedule appointments during calls

## Security Notes

- **Never commit `credentials.json` or `token.json` to git** - they're in `.gitignore`
- Keep your OAuth credentials secure
- The `token.json` file contains sensitive access tokens - keep it private
- If credentials are compromised, revoke them in Google Cloud Console and create new ones


