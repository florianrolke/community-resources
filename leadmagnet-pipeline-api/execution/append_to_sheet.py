#!/usr/bin/env python3
"""
Append rows to an existing Google Sheet.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Load environment variables
load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def extract_sheet_id(url):
    """Extract the Google Sheet ID from a URL."""
    if '/d/' in url:
        return url.split('/d/')[1].split('/')[0]
    return url


def get_credentials():
    """Get OAuth2 credentials for Google Sheets API."""
    creds = None

    if os.path.exists('token.json'):
        try:
            with open('token.json', 'r') as token:
                token_data = json.load(token)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print(f"Error loading token: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def append_rows(sheet_url, json_file, worksheet_name=None):
    """
    Append rows from JSON file to an existing Google Sheet.

    Args:
        sheet_url: Google Sheets URL or ID
        json_file: Path to JSON file with rows to append
        worksheet_name: Name of the specific worksheet (default: first sheet)

    Returns:
        Number of rows appended
    """
    try:
        # Read JSON data
        with open(json_file, 'r') as f:
            data = json.load(f)

        if not data:
            print("No data in JSON file.")
            return 0

        # Authenticate
        creds = get_credentials()
        client = gspread.authorize(creds)

        # Open the spreadsheet
        sheet_id = extract_sheet_id(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)

        # Get the worksheet
        if worksheet_name:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            worksheet = spreadsheet.sheet1

        # Get existing headers
        existing_headers = worksheet.row_values(1)

        if not existing_headers:
            print("Sheet has no headers. Please add headers first.")
            return 0

        # Append each row
        rows_appended = 0
        for record in data:
            # Build row in correct column order
            row = []
            for header in existing_headers:
                value = record.get(header, "")
                row.append(value)

            worksheet.append_row(row, value_input_option='RAW')
            rows_appended += 1
            print(f"Appended row: {record.get('ID', 'Unknown')}")

        print(f"\nSuccessfully appended {rows_appended} row(s) to the sheet.")
        return rows_appended

    except Exception as e:
        print(f"Error appending to sheet: {str(e)}", file=sys.stderr)
        return 0


def main():
    parser = argparse.ArgumentParser(description="Append rows to a Google Sheet")
    parser.add_argument("--url", required=True, help="Google Sheets URL or ID")
    parser.add_argument("--json_file", required=True, help="Path to JSON file with rows to append")
    parser.add_argument("--worksheet", help="Name of the worksheet (default: first sheet)")

    args = parser.parse_args()

    result = append_rows(args.url, args.json_file, args.worksheet)

    if result > 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
