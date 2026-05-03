"""Pytest fixtures shared across the MT5 Bridge API test suite."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mt5_bridge.models.db.base import Base


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    """In-memory SQLite async session for unit tests.

    Uses aiosqlite so no PostgreSQL instance is required during CI.
    Each test function gets a fresh, isolated database.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture()
def mock_mt5_conn() -> MagicMock:
    """Mock MT5Connection with an async run() dispatcher.

    Returns a MagicMock that mimics the MT5Connection interface.
    Individual tests override `mock_mt5_conn.run` as an AsyncMock with the
    return values they need.
    """
    conn = MagicMock()
    conn.is_connected = True
    conn.run = AsyncMock()
    return conn
