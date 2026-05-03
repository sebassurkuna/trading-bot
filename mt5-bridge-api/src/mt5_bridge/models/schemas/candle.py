"""Pydantic schemas for OHLCV candle data."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CandleSchema(BaseModel):
    """Single OHLCV candle bar.

    Attributes:
        time:        Bar open time (UTC).
        open:        Opening price.
        high:        Highest price in the bar.
        low:         Lowest price in the bar.
        close:       Closing price.
        tick_volume: Number of ticks during the bar.
        spread:      Spread value at bar open.
    """

    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int


class CandlesResponse(BaseModel):
    """Response for GET /api/v1/tick/{symbol}.

    Attributes:
        symbol:  MT5 symbol.
        period:  Requested candle period (e.g. '1h').
        count:   Total number of candles returned.
        candles: List of OHLCV bars ordered by time ascending.
    """

    symbol: str
    period: str
    count: int
    candles: list[CandleSchema]
