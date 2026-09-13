"""
CommitmentOS — Generate Gmail Refresh Token via CLI.
"""
import os
import re
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# Root directory
ROOT_DIR = Path(__file__).resolve().parent.parent

# Read client ID and secret from environment or .env files
def get_env_var(key: str) -> str:
    val = os.environ.get(key, "")
    if val:
        return val
    for env_path in [ROOT_DIR / ".env", ROOT_DIR / "apps" / "api" / ".env"]:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
    return ""

def main():
    client_id = get_env_var("GMAIL_CLIENT_ID")
    client_secret = get_env_var("GMAIL_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("ERROR: GMAIL_CLIENT_ID or GMAIL_CLIENT_SECRET is missing from .env")
        sys.exit(1)

    scopes = [
        "https://www.googleapis.com/auth/gmail.readonly"
    ]

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }

    print("=" * 60, flush=True)
    print("Starting Gmail OAuth authorization flow...", flush=True)
    print("A browser window will open automatically for you to log in.", flush=True)
    print("=" * 60 + "\n", flush=True)

    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes
    )

    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent"
    )

    refresh_token = credentials.refresh_token

    print("\n========================================")
    print("GMAIL REFRESH TOKEN:")
    print("========================================")
    print(refresh_token)
    print("========================================")

    if refresh_token:
        # Update both root .env and apps/api/.env
        for env_path in [ROOT_DIR / ".env", ROOT_DIR / "apps" / "api" / ".env"]:
            if env_path.exists():
                content = env_path.read_text(encoding="utf-8")
                if re.search(r"^GMAIL_REFRESH_TOKEN=.*$", content, flags=re.MULTILINE):
                    new_content = re.sub(
                        r"^GMAIL_REFRESH_TOKEN=.*$",
                        f"GMAIL_REFRESH_TOKEN={refresh_token}",
                        content,
                        flags=re.MULTILINE,
                    )
                else:
                    new_content = content + f"\nGMAIL_REFRESH_TOKEN={refresh_token}\n"
                env_path.write_text(new_content, encoding="utf-8")
                print(f"Updated {env_path.relative_to(ROOT_DIR)}")
        print("\nSuccessfully saved GMAIL_REFRESH_TOKEN to .env files!")
    else:
        print("\nWARNING: Google did not return a refresh token.")
        print("Ensure access_type='offline' and prompt='consent' were used.")


if __name__ == "__main__":
    main()
