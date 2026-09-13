"""CommitmentOS — root configuration proxy.

Exposes Settings and settings from apps/api/config.py so that modules
can import `from config import settings` regardless of current working directory.
"""
import os
import sys

_api_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "apps", "api"))
if _api_path not in sys.path:
    sys.path.insert(0, _api_path)

from apps.api.config import Settings, settings  # noqa: E402

__all__ = ["Settings", "settings"]
