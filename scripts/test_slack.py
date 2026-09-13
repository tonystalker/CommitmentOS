import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from integrations.slack.client import SlackClient

async def main():
    client = SlackClient()
    try:
        resp = await client._client.auth_test()
        print("Slack Auth SUCCESS!")
        print(f"Bot user: {resp.get('user')}")
        print(f"Team: {resp.get('team')}")
        print(f"Scopes: {resp.headers.get('x-oauth-scopes')}")
    except Exception as e:
        print(f"Slack Auth FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
