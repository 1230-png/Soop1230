"""One-time local script to obtain a YouTube upload refresh token.

Run this on your own machine, once, using the CLIENT_ID and CLIENT_SECRET
from Google Cloud Console (APIs & Services > Credentials).

    pip install google-auth-oauthlib
    python3 get_refresh_token.py --client-id YOUR_ID --client-secret YOUR_SECRET
"""

import argparse

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


if __name__ == "__main__":
    main()
