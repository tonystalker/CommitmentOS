"""CommitmentOS — root database proxy.

Exposes Base, engine, AsyncSessionLocal, get_db, and init_db so that
domain models and agent modules can import `from database import Base`
regardless of whether the application is executed from root or apps/api.
"""
import os
import sys

_api_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "apps", "api"))
if _api_path not in sys.path:
    sys.path.insert(0, _api_path)

from apps.api.database import (  # noqa: E402
    AsyncSessionLocal,
    Base,
    engine,
    get_db,
    init_db,
)

__all__ = [
    "AsyncSessionLocal",
    "Base",
    "engine",
    "get_db",
    "init_db",
]
