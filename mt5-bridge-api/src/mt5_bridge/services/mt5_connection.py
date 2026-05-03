"""MT5 connection singleton with thread-safe dispatcher for async FastAPI usage."""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

import MetaTrader5 as mt5

from mt5_bridge.config import Settings
from mt5_bridge.exceptions.mt5_exceptions import MT5ConnectionError

logger = logging.getLogger(__name__)
T = TypeVar("T")


class MT5Connection:
    """Thread-safe singleton wrapping the MetaTrader5 Python library.

    MT5 requires initialize() in the SAME thread as all trading operations.
    Uses a single-worker ThreadPoolExecutor to ensure thread affinity.
    """

    _instance: MT5Connection | None = None
    _singleton_lock: threading.Lock = threading.Lock()

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mt5-worker")
        self._is_connected = False
        self._worker_thread_id: int | None = None

    # ------------------------------------------------------------------
    # Singleton factory
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls, settings: Settings) -> "MT5Connection":
        """Return the process-wide MT5Connection singleton."""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls(settings)
        return cls._instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_mt5_in_worker(self) -> None:
        """Initialize MT5 inside the worker thread."""
        self._worker_thread_id = threading.current_thread().ident
        logger.info(
            "Initializing MT5 (thread_id=%s, login=%s, server=%s)",
            self._worker_thread_id,
            self._settings.mt5_login,
            self._settings.mt5_server,
        )

        kwargs: dict[str, Any] = {
            "login": self._settings.mt5_login,
            "password": self._settings.mt5_password,
            "server": self._settings.mt5_server,
            "timeout": self._settings.mt5_timeout,
        }
        if self._settings.mt5_path:
            kwargs["path"] = self._settings.mt5_path

        if not mt5.initialize(**kwargs):
            code, description = mt5.last_error()
            raise MT5ConnectionError(
                f"mt5.initialize() failed — code={code}, description={description}"
            )

        info = mt5.account_info()
        logger.info(
            "MT5 connected — account=%s, broker=%s, server=%s",
            info.login if info else "?",
            info.company if info else "?",
            info.server if info else "?",
        )

    def connect(self) -> None:
        """Initialize and authenticate with the MT5 terminal."""
        future = self._executor.submit(self._init_mt5_in_worker)
        future.result()
        self._is_connected = True

    def _shutdown_mt5_in_worker(self) -> None:
        mt5.shutdown()

    def disconnect(self) -> None:
        """Shut down MT5 connection and worker thread pool."""
        if self._is_connected:
            future = self._executor.submit(self._shutdown_mt5_in_worker)
            future.result()
        self._is_connected = False
        self._executor.shutdown(wait=True)
        logger.info("MT5 connection closed.")

    @property
    def is_connected(self) -> bool:
        """Return True if the MT5 terminal connection is active."""
        return self._is_connected

    # ------------------------------------------------------------------
    # Async dispatcher
    # ------------------------------------------------------------------

    async def run(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a blocking MT5 function in the dedicated worker thread."""
        if not self._is_connected:
            raise MT5ConnectionError("MT5 terminal is not connected.")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, lambda: fn(*args, **kwargs)
        )

    async def order_send(self, request: dict) -> Any:
        """Execute mt5.order_send (requires direct call without wrappers)."""
        if not self._is_connected:
            raise MT5ConnectionError("MT5 terminal is not connected.")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, lambda: mt5.order_send(request)
        )

    async def order_check(self, request: dict) -> Any:
        """Execute mt5.order_check (requires direct call without wrappers)."""
        if not self._is_connected:
            raise MT5ConnectionError("MT5 terminal is not connected.")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, lambda: mt5.order_check(request)
        )
