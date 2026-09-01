"""One-time local script to obtain a YouTube refresh token for @Rush22.

Run this on your own machine (never in CI), once, while logged into the
Google account that manages @Rush22-i8p. See ../SETUP.md.

    pip install -r requirements.txt
    python scripts/get_refresh_token.py --client-id "..." --client-secret "..."

The token is verified against the live API before it is saved, because the
usual failure mode is a token that was mistyped while being copied into
repository secrets and only fails later, inside a scheduled run.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env.youtube"
SCOPES = ["https://www.googleapis.com/auth/youtube"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id")
    parser.add_argument("--client-secret")
    parser.add_argument(
        "--client-secret-file",
        help="client_secret.json downloaded from Google Cloud Console "
             "(alternative to --client-id/--client-secret)",
    )
    args = parser.parse_args()

    if args.client_secret_file:
        flow = InstalledAppFlow.from_client_secrets_file(args.client_secret_file, SCOPES)
    elif args.client_id and args.client_secret:
        config = {
            "installed": {
                "client_id": args.client_id,
                "client_secret": args.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            temp_path = f.name
        flow = InstalledAppFlow.from_client_secrets_file(temp_path, SCOPES)
        Path(temp_path).unlink()
    else:
        raise SystemExit(
            "Pass either --client-secret-file, or both --client-id and --client-secret."
        )

    print("A browser window will open. Sign in with the account that manages @Rush22-i8p.")
    creds = flow.run_local_server(port=0)

    # Verify before saving, and show which channel it actually authorized —
    # signing in with the wrong Google account is the other common mistake.
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        print("❌ These credentials are not attached to any YouTube channel.", file=sys.stderr)
        return 1

    channel_id = items[0]["id"]
    handle = items[0]["snippet"].get("customUrl", "(no handle)")
    title = items[0]["snippet"].get("title", "?")
    print(f"\n✅ Refresh token verified working — {title} ({handle}, {channel_id})")
    if handle.lower() != "@rush22-i8p":
        print(
            f"⚠️  This is NOT @rush22-i8p. Uploads will refuse to run unless you "
            f"either sign in with the right account or set RUSH_CHANNEL_ID={channel_id}.",
            file=sys.stderr,
        )

    ENV_FILE.write_text(
        f"RUSH_CLIENT_ID={creds.client_id}\n"
        f"RUSH_CLIENT_SECRET={creds.client_secret}\n"
        f"RUSH_REFRESH_TOKEN={creds.refresh_token}\n"
        f"RUSH_CHANNEL_ID={channel_id}\n",
        encoding="utf-8",
    )
    print(f"💾 Saved to {ENV_FILE} (gitignored)")

    print("\nAdd these as GitHub repository secrets:\n")
    print(f"RUSH_CLIENT_ID      {creds.client_id}")
    print(f"RUSH_CLIENT_SECRET  {creds.client_secret}")
    print(f"RUSH_REFRESH_TOKEN  {creds.refresh_token}")
    print(f"RUSH_CHANNEL_ID     {channel_id}   (optional but recommended)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
