
import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def main():
    token_file = 'token.json'
    if not os.path.exists(token_file):
        # try also google_sheets_token.json
        token_file = 'google_sheets_token.json'
    
    if not os.path.exists(token_file):
        print("No token file found.")
        return

    with open(token_file, 'r') as f:
        token_data = json.load(f)
    
    creds = Credentials.from_authorized_user_info(token_data)
    service = build('sheets', 'v4', credentials=creds)
    spreadsheet_id = '12wHDiAFCFKdXSfxdbyw6UhQSPxe8eZt3ehjzTDv2-Jo'
    
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        print("Valid Sheet Names found in this spreadsheet:")
        for sheet in sheets:
            title = sheet.get('properties', {}).get('title')
            sheet_id = sheet.get('properties', {}).get('sheetId')
            print(f"- '{title}' (ID: {sheet_id})")
    except HttpError as err:
        print(f"HTTP Error: {err}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
