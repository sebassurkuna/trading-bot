"""Domain-specific exceptions for the MT5 Bridge API."""

from __future__ import annotations


class MT5BridgeError(Exception):
    """Base class for all MT5 Bridge domain errors."""


class MT5ConnectionError(MT5BridgeError):
    """Raised when the MT5 terminal connection fails or is unavailable."""


class MT5OrderError(MT5BridgeError):
    """Raised when an MT5 order operation is rejected or returns an error retcode.

    Attributes:
        retcode: The MT5 retcode returned by order_send(), or None if unavailable.
    """

    def __init__(self, message: str, retcode: int | None = None) -> None:
        super().__init__(message)
        self.retcode = retcode


class DuplicateOrderError(MT5BridgeError):
    """Raised when an order_id has already been processed (idempotency guard).

    Attributes:
        order_id: The duplicated client-side UUID string.
    """

    def __init__(self, order_id: str) -> None:
        super().__init__(f"Order '{order_id}' has already been processed.")
        self.order_id = order_id


class OrderNotFoundError(MT5BridgeError):
    """Raised when the requested order_id is not found in the local registry.

    Attributes:
        order_id: The missing UUID string.
    """

    def __init__(self, order_id: str) -> None:
        super().__init__(f"Order '{order_id}' not found.")
        self.order_id = order_id


class MT5SymbolError(MT5BridgeError):
    """Raised when the requested symbol is not available in the MT5 terminal.

    Attributes:
        symbol: The symbol that could not be resolved.
    """

    def __init__(self, symbol: str) -> None:
        super().__init__(f"Symbol '{symbol}' is not available or not found.")
        self.symbol = symbol
