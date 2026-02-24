"""
auth_youtube.py — One-time YouTube OAuth setup.

Run this script ONCE from your local machine to generate token.pickle.
A browser window will open — sign in with the Google account that
owns your YouTube channel and click "Allow".

The resulting token.pickle is saved in the project root and will be
used by youtube_uploader.py for all future uploads (including in
GitHub Actions via a base64-encoded Secret).

Usage:
    python auth_youtube.py

Requirements:
    - client_secret.json must exist in the project root.
      Download it from Google Cloud Console:
      https://console.cloud.google.com/apis/credentials
      (Create > OAuth 2.0 Client ID > Desktop App > Download JSON)
"""

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes required for uploading videos
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CLIENT_SECRET_FILE = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
TOKEN_PATH = "token.pickle"


def main():
    credentials = None

    # If we already have a valid token, just refresh it
    if os.path.exists(TOKEN_PATH):
        print("🔑 Found existing token.pickle — checking validity...")
        with open(TOKEN_PATH, "rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("🔄 Refreshing expired token...")
            credentials.refresh(Request())
        else:
            # Full browser-based OAuth flow
            if not os.path.exists(CLIENT_SECRET_FILE):
                print(
                    f"\n❌ ERROR: '{CLIENT_SECRET_FILE}' not found.\n\n"
                    "  1. Go to: https://console.cloud.google.com/apis/credentials\n"
                    "  2. Click 'Create Credentials' → 'OAuth 2.0 Client ID'\n"
                    "  3. Application type: Desktop App\n"
                    "  4. Download the JSON and save it as 'client_secret.json'\n"
                    "     in this project folder.\n"
                    "  5. Also enable 'YouTube Data API v3' in the API library.\n"
                )
                return

            print("\n🌐 Opening browser for Google sign-in...")
            print("   Sign in with the Google account that owns your YouTube channel.")
            print("   Then click 'Allow' to grant upload permission.\n")

            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)

        # Save the credentials for reuse
        with open(TOKEN_PATH, "wb") as token:
            pickle.dump(credentials, token)
        print(f"\n✅ token.pickle saved successfully!\n")

    print("🎉 YouTube authentication is set up and ready.")
    print("   You can now run: python main.py")
    print()
    print("📦 For GitHub Actions, encode the token with:")
    print("   PowerShell: [Convert]::ToBase64String([IO.File]::ReadAllBytes('token.pickle'))")
    print("   Then paste the result as a GitHub Secret named: YOUTUBE_TOKEN_B64")


if __name__ == "__main__":
    main()
