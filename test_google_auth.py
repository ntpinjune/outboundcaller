#!/usr/bin/env python3
"""Test script to authenticate with Google Calendar API."""

import os
from google_calendar import GoogleCalendar
import logging

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("Google Calendar Authentication Test")
    print("=" * 60)
    
    # Check if credentials.json exists
    if not os.path.exists("credentials.json"):
        print("\n❌ ERROR: credentials.json not found!")
        print("\nPlease download it from Google Cloud Console:")
        print("1. Go to: https://console.cloud.google.com/apis/credentials")
        print("2. Create an OAuth 2.0 Client ID (Desktop application)")
        print("3. Download the JSON file and save it as 'credentials.json'")
        return
    
    print("\n✓ credentials.json found")
    
    # Check if token.json exists
    if os.path.exists("token.json"):
        print("✓ token.json found (you may already be authenticated)")
    else:
        print("ℹ token.json not found (will need to authenticate)")
    
    print("\n" + "=" * 60)
    print("Attempting to authenticate...")
    print("A browser window should open for Google sign-in.")
    print("If it doesn't open automatically, check the terminal for a URL.")
    print("=" * 60 + "\n")
    
    try:
        # Create GoogleCalendar instance - this will trigger authentication
        calendar = GoogleCalendar()
        
        # Force authentication by trying to access credentials
        calendar._ensure_authenticated()
        
        if calendar.creds and calendar.creds.valid:
            print("\n✅ SUCCESS! Authentication completed!")
            print("✓ Credentials are valid")
            print("✓ token.json has been created/updated")
            print("\nYou can now use the Google Calendar integration in your agent.")
        else:
            print("\n❌ Authentication failed - credentials are not valid")
            
    except FileNotFoundError as e:
        print(f"\n❌ ERROR: {e}")
    except Exception as e:
        print(f"\n❌ ERROR during authentication: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure credentials.json is valid")
        print("2. Check that you have internet access")
        print("3. Verify the OAuth consent screen is configured in Google Cloud Console")
        print("4. Make sure the Calendar API is enabled in your Google Cloud project")

if __name__ == "__main__":
    main()



