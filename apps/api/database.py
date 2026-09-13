"""
CommitmentOS — async SQLAlchemy engine + session factory.
Schema created via create_all() on startup — no Alembic.
"""
# ruff: noqa: E402
import logging
import sys
from pathlib import Path
from typing import AsyncGenerator

# Ensure root directory and apps/api are in sys.path
_root = Path(__file__).resolve().parent.parent.parent
_api_dir = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _create_engine_instance(url: str):
    if "sqlite" in url.lower():
        return create_async_engine(
            url,
            echo=settings.environment == "development",
        )
    connect_args = {}
    if "pooler.supabase.com" in url or "pgbouncer" in url.lower():
        connect_args["statement_cache_size"] = 0

    return create_async_engine(
        url,
        echo=settings.environment == "development",
        pool_pre_ping=True,
        connect_args=connect_args,
    )


engine = _create_engine_instance(settings.database_url)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables on startup. Safe to call multiple times (IF NOT EXISTS semantics).

    If the primary database (e.g. Postgres) fails to connect, automatically falls back
    to a local SQLite database (sqlite+aiosqlite:///commitmentos.db) so the API and app
    can run without crashing.
    """
    global engine, AsyncSessionLocal
    from commitments import models as _  # noqa: F401 — registers all models before create_all

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        if "sqlite" not in settings.database_url.lower():
            logger.warning(
                "Primary database connection failed (%s): %s. Falling back to local SQLite database (commitmentos.db).",
                settings.database_url,
                e,
            )
            sqlite_url = "sqlite+aiosqlite:///commitmentos.db"
            engine = _create_engine_instance(sqlite_url)
            AsyncSessionLocal.configure(bind=engine)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema initialized with SQLite fallback at commitmentos.db.")
        else:
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

