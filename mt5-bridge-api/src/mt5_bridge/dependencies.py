"""FastAPI dependency providers.

All dependencies read their dependencies from `request.app.state`,
which is populated during the application lifespan in `main.py`.
This design avoids module-level side effects (no engine creation at import
time) and makes tests straightforward — just set the desired objects on a
mock app.state.
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from mt5_bridge.services.mt5_connection import MT5Connection


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh AsyncSession per HTTP request.

    The session is automatically returned to the pool when the request
    completes (or raises an exception).

    Args:
        request: The current FastAPI request (injected by the DI framework).

    Yields:
        An open AsyncSession bound to the application's connection pool.
    """
    async with request.app.state.session_factory() as session:
        yield session


def get_mt5(request: Request) -> MT5Connection:
    """Return the process-wide MT5Connection singleton stored on app.state.

    Args:
        request: The current FastAPI request.

    Returns:
        The MT5Connection singleton.
    """
    return request.app.state.mt5_conn
