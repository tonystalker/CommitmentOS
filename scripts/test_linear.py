import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from integrations.linear.client import LinearClient

async def main():
    print("Testing Linear API integration...")
    client = LinearClient()
    try:
        data = await client._query("""
            query {
                viewer { id name email }
                teams { nodes { id name key } }
            }
        """)
        viewer = data.get("viewer", {})
        teams = data.get("teams", {}).get("nodes", [])
        print("Linear Auth SUCCESS!")
        print(f"Connected User: {viewer.get('name')} ({viewer.get('email')})")
        print(f"Available Teams: {len(teams)}")
        for team in teams:
            print(f"  - Team '{team.get('name')}' (Key: {team.get('key')}, ID: {team.get('id')})")
    except Exception as e:
        print(f"Linear Auth FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
