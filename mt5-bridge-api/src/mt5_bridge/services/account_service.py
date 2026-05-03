"""Service for retrieving MT5 account information."""

from __future__ import annotations

import logging

import MetaTrader5 as mt5

from mt5_bridge.exceptions.mt5_exceptions import MT5ConnectionError
from mt5_bridge.models.schemas.account import AccountInfoResponse
from mt5_bridge.services.mt5_connection import MT5Connection

logger = logging.getLogger(__name__)


class AccountService:
    """Provides live account details from the connected MT5 terminal."""

    def __init__(self, connection: MT5Connection) -> None:
        self._conn = connection

    async def get_account_info(self) -> AccountInfoResponse:
        """Fetch current account details from MT5.

        Returns:
            AccountInfoResponse populated with live data.

        Raises:
            MT5ConnectionError: if the terminal is unreachable or returns no data.
        """
        info = await self._conn.run(mt5.account_info)
        if info is None:
            code, desc = mt5.last_error()
            raise MT5ConnectionError(
                f"mt5.account_info() returned None — code={code}, description={desc}"
            )

        return AccountInfoResponse(
            account_id=info.login,
            name=info.name,
            broker=info.company,
            currency=info.currency,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            margin_level=info.margin_level,
            leverage=info.leverage,
            is_trade_allowed=bool(info.trade_allowed),
            server=info.server,
        )
