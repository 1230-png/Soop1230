"""One-time local script to obtain a YouTube upload refresh token.

Run this on your own machine (NOT in CI), once, after downloading
client_secret.json from Google Cloud Console. See ../SETUP.md step 5.

    pip install google-auth-oauthlib
    python3 get_refresh_token.py --client-secret client_secret.json
"""

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-secret", default="client_secret.json")
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES)
    credentials = flow.run_local_server(port=0)

    print("\nSave these as GitHub repository secrets (see SETUP.md step 6):\n")
    print(f"client_id:     {credentials.client_id}")
    print(f"client_secret: {credentials.client_secret}")
    print(f"refresh_token: {credentials.refresh_token}")


if __name__ == "__main__":
    main()
