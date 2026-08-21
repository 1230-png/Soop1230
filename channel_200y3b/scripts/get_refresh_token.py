"""One-time local script to obtain a YouTube upload refresh token.

Run this on your own machine, once, using the CLIENT_ID and CLIENT_SECRET
from Google Cloud Console (APIs & Services > Credentials).

    pip install google-auth-oauthlib
    python3 get_refresh_token.py --client-id YOUR_ID --client-secret YOUR_SECRET
"""

import argparse

import requests
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    args = parser.parse_args()

    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(port=0)

    print("\nSave these as environment variables / GitHub secrets:\n")
    print(f"YT_CLIENT_ID:     {credentials.client_id}")
    print(f"YT_CLIENT_SECRET: {credentials.client_secret}")
    print(f"YT_REFRESH_TOKEN: {credentials.refresh_token}")

    print("\nVerifying refresh token works (separate call, no manual copy)...")
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "grant_type": "refresh_token",
        },
    )
    print(f"Verification status: {resp.status_code}")
    print(resp.text)
    if resp.status_code == 200:
        print("\n✅ Refresh token verified working.")
    else:
        print("\n❌ Refresh token verification FAILED — see response above.")


if __name__ == "__main__":
    main()
