"""CommitmentOS — Root entrypoint for get_gmail_token.py."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    script_path = Path(__file__).resolve().parent / "scripts" / "get_gmail_token.py"
    runpy.run_path(str(script_path), run_name="__main__")

