
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def main():
    token_file = 'token.json'
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, ['https://www.googleapis.com/auth/spreadsheets'])
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("No valid tokens found. Please run the app to authenticate.")
            return

    service = build('sheets', 'v4', credentials=creds)
    spreadsheet_id = '12wHDiAFCFKdXSfxdbyw6UhQSPxe8eZt3ehjzTDv2-Jo'
    
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        print(f"Spreadsheet Title: {spreadsheet.get('properties', {}).get('title')}")
        print("Sheets found:")
        for sheet in sheets:
            props = sheet.get('properties', {})
            print(f"- {props.get('title')} (ID: {props.get('sheetId')})")
    except HttpError as err:
        print(f"HTTP Error: {err}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
