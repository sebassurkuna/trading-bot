"""Service for fetching historical OHLCV candles from MT5."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import MetaTrader5 as mt5

from mt5_bridge.exceptions.mt5_exceptions import MT5ConnectionError, MT5SymbolError
from mt5_bridge.models.schemas.candle import CandleSchema, CandlesResponse
from mt5_bridge.services.mt5_connection import MT5Connection

logger = logging.getLogger(__name__)

# Mapping from human-readable period strings to MT5 TIMEFRAME constants.
_TIMEFRAME_MAP: dict[str, int] = {
    "1m": mt5.TIMEFRAME_M1,
    "5m": mt5.TIMEFRAME_M5,
    "15m": mt5.TIMEFRAME_M15,
    "30m": mt5.TIMEFRAME_M30,
    "1h": mt5.TIMEFRAME_H1,
    "4h": mt5.TIMEFRAME_H4,
    "1d": mt5.TIMEFRAME_D1,
    "1w": mt5.TIMEFRAME_W1,
}

VALID_PERIODS = list(_TIMEFRAME_MAP.keys())


def _to_utc_timestamp(dt: datetime) -> int:
    """Convert a datetime to a UTC Unix timestamp.

    Timezone-aware datetimes are properly converted to UTC.
    Naive datetimes are assumed to already be in UTC.

    Args:
        dt: The datetime to convert.

    Returns:
        UTC Unix timestamp as integer.
    """
    if dt.tzinfo is not None:
        return int(dt.timestamp())
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


class CandleService:
    """Fetches historical OHLCV data from MT5 for backtesting purposes."""

    def __init__(self, connection: MT5Connection) -> None:
        self._conn = connection

    def _resolve_timeframe(self, period: str) -> int:
        """Map a period string to an MT5 TIMEFRAME constant.

        Args:
            period: Human-readable period, e.g. '1h', '4h', '1d'.

        Returns:
            Corresponding MT5 TIMEFRAME_* integer constant.

        Raises:
            ValueError: if the period string is not in VALID_PERIODS.
        """
        timeframe = _TIMEFRAME_MAP.get(period.lower())
        if timeframe is None:
            valid = ", ".join(VALID_PERIODS)
            raise ValueError(f"Unknown period '{period}'. Valid options: {valid}.")
        return timeframe

    async def get_candles(
        self,
        symbol: str,
        period: str,
        date_from: datetime,
        date_to: datetime,
    ) -> CandlesResponse:
        """Retrieve OHLCV candles for a symbol within a date range.

        Args:
            symbol:    MT5 symbol with broker suffix, e.g. 'EURUSDm'.
            period:    Candle period string, e.g. '1h'.
            date_from: Start of the range (UTC-aware or naive UTC).
            date_to:   End of the range (UTC-aware or naive UTC).

        Returns:
            CandlesResponse with the list of candles ordered by time ascending.

        Raises:
            ValueError:         if the period string is invalid.
            MT5SymbolError:     if the symbol does not exist in MT5.
            MT5ConnectionError: if MT5 returns an unexpected error.
        """
        timeframe = self._resolve_timeframe(period)

        # Verify the symbol exists before attempting to fetch rates.
        symbol_info = await self._conn.run(mt5.symbol_info, symbol)
        if symbol_info is None:
            raise MT5SymbolError(symbol)

        # Convert to UTC Unix timestamps — timezone-unambiguous for MT5.
        # Timezone-aware datetimes are converted correctly; naive datetimes
        # are assumed to already be UTC (never local/Ecuador time).
        from_ts = _to_utc_timestamp(date_from)
        to_ts = _to_utc_timestamp(date_to)

        rates = await self._conn.run(mt5.copy_rates_range, symbol, timeframe, from_ts, to_ts)

        if rates is None:
            code, desc = mt5.last_error()
            raise MT5ConnectionError(
                f"copy_rates_range() failed for '{symbol}' — code={code}, description={desc}"
            )

        candles = [
            CandleSchema(
                time=datetime.fromtimestamp(int(row["time"]), tz=timezone.utc),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                tick_volume=int(row["tick_volume"]),
                spread=int(row["spread"]),
            )
            for row in rates
        ]

        logger.debug("Fetched %d candles for %s [%s].", len(candles), symbol, period)
        return CandlesResponse(symbol=symbol, period=period, count=len(candles), candles=candles)
