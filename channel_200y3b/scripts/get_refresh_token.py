"""One-time local script to obtain a YouTube upload refresh token.

Run this on your own machine (Windows/Mac/Linux), once:

    pip install google-auth-oauthlib requests
    python get_refresh_token.py --client-secret client_secret.json

The script will:
1. Open a browser for you to authorize with your YouTube (@200-y3b) account
2. Extract client_id and client_secret from the JSON file
3. Get a refresh_token that never expires
4. Output the 3 secrets to copy into GitHub repository Secrets
"""

import argparse
import json
from pathlib import Path

import requests
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]
ENV_FILE = Path(__file__).resolve().parent.parent / ".env.youtube"


def load_client_config(client_secret_path):
    """Load and sanity-check Google Cloud Console's downloaded JSON file.

    Returns the whole document, not the inner block: InstalledAppFlow expects
    the "installed"/"web" wrapper key to still be there and raises a confusing
    "Client secrets must be for a web or installed app" if it is unwrapped.
    """
    with open(client_secret_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    if "installed" not in data and "web" not in data:
        raise SystemExit(
            f"{client_secret_path} is not an OAuth client file — it has no "
            "'installed' or 'web' key. Re-download it from Google Cloud Console "
            "(APIs & Services > Credentials > your OAuth client > download icon)."
        )
    return data


def main():
    parser = argparse.ArgumentParser(description="Get YouTube refresh token from Google OAuth credentials")
    parser.add_argument("--client-secret", default="client_secret.json",
                        help="Path to client_secret.json from Google Cloud Console (default: client_secret.json)")
    args = parser.parse_args()

    client_secret_file = Path(args.client_secret)
    if not client_secret_file.exists():
        raise SystemExit(f"❌ File not found: {client_secret_file}\n"
                        "Download client_secret.json from:\n"
                        "  https://console.cloud.google.com/apis/credentials?project=y3b-506009")

    print(f"📖 Reading credentials from: {client_secret_file}")
    client_config = load_client_config(client_secret_file)

    print("🔗 Opening browser for authorization...\n")
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(port=0)

    # Prove the refresh token actually mints an access token before anyone
    # copies it into GitHub Secrets. Without this check a token that is
    # subtly wrong only shows up much later, as an invalid_grant inside a
    # CI upload, where it looks like a pipeline bug rather than a bad paste.
    print("\nVerifying the refresh token works...")
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "grant_type": "refresh_token",
        },
    )
    if resp.status_code != 200:
        raise SystemExit(f"Refresh token verification FAILED ({resp.status_code}):\n{resp.text}")
    print("Verified: the token mints an access token.")

    # Write them to a file too. Copying a ~100-character refresh token out of
    # a terminal by dragging across a wrapped line is how stray newlines get
    # into the secret; opening this file and copying each line is not.
    ENV_FILE.write_text(
        f"Y3B_CLIENT_ID={credentials.client_id}\n"
        f"Y3B_CLIENT_SECRET={credentials.client_secret}\n"
        f"Y3B_REFRESH_TOKEN={credentials.refresh_token}\n",
        encoding="utf-8",
    )

    print("\n" + "=" * 70)
    print("SUCCESS — the 3 values were written to:")
    print(f"  {ENV_FILE}")
    print("Open that file, and copy each value (the part after '=') into the")
    print("matching GitHub repository Secret. Do not retype them by hand.")
    print("=" * 70)



if __name__ == "__main__":
    main()
