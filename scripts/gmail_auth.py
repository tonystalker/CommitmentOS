"""
Gmail one-time auth script.

Run this once to generate a refresh token, then add it to your .env:
  GMAIL_REFRESH_TOKEN=<value from token.json>

Usage:
  pip install google-auth-oauthlib google-auth-httplib2
  python scripts/gmail_auth.py

You need a Google Cloud project with Gmail API enabled.
Download credentials.json from https://console.cloud.google.com/apis/credentials
and place it in this directory before running.
"""
import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]

TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"


def main() -> None:
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    token_data = json.loads(creds.to_json())
    print("\n✅ Auth successful! Add these to your .env file:\n")
    print(f"GMAIL_CLIENT_ID={token_data.get('client_id', '')}")
    print(f"GMAIL_CLIENT_SECRET={token_data.get('client_secret', '')}")
    print(f"GMAIL_REFRESH_TOKEN={token_data.get('refresh_token', '')}")
    print(f"\nFull token saved to: {TOKEN_PATH}")
    print("Do NOT commit token.json to version control.")


if __name__ == "__main__":
    main()
