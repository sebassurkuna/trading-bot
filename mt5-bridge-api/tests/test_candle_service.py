"""Unit tests for CandleService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from mt5_bridge.exceptions.mt5_exceptions import MT5SymbolError
from mt5_bridge.services.candle_service import CandleService, _to_utc_timestamp

# Reusable date range
_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
_TO = datetime(2026, 2, 1, tzinfo=timezone.utc)


def _make_rates(n: int = 2) -> np.ndarray:
    """Build a minimal numpy array of OHLCV rows as returned by MT5."""
    rows = [
        (1706745600 + i * 3600, 1.105 + i * 0.001, 1.108, 1.103, 1.1065, 5678, 2, 0)
        for i in range(n)
    ]
    return np.array(
        rows,
        dtype=[
            ("time", "i8"),
            ("open", "f8"),
            ("high", "f8"),
            ("low", "f8"),
            ("close", "f8"),
            ("tick_volume", "i8"),
            ("spread", "i4"),
            ("real_volume", "i8"),
        ],
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_candles_success(mock_mt5_conn: MagicMock) -> None:
    """Should return a correctly mapped CandlesResponse."""
    rates = _make_rates(n=3)
    symbol_info_mock = MagicMock()
    # First run() → symbol_info; second → copy_rates_range
    mock_mt5_conn.run = AsyncMock(side_effect=[symbol_info_mock, rates])

    service = CandleService(mock_mt5_conn)
    result = await service.get_candles("EURUSDm", "1h", _FROM, _TO)

    assert result.symbol == "EURUSDm"
    assert result.period == "1h"
    assert result.count == 3
    assert result.candles[0].open == pytest.approx(1.105)
    assert result.candles[0].tick_volume == 5678


@pytest.mark.asyncio
async def test_get_candles_all_periods(mock_mt5_conn: MagicMock) -> None:
    """Every valid period string must resolve without raising ValueError."""
    valid_periods = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    rates = _make_rates(n=1)
    symbol_info_mock = MagicMock()

    service = CandleService(mock_mt5_conn)

    for period in valid_periods:
        mock_mt5_conn.run = AsyncMock(side_effect=[symbol_info_mock, rates])
        result = await service.get_candles("EURUSDm", period, _FROM, _TO)
        assert result.period == period


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_candles_invalid_period(mock_mt5_conn: MagicMock) -> None:
    """An unsupported period string must raise ValueError before any MT5 call."""
    mock_mt5_conn.run = AsyncMock()
    service = CandleService(mock_mt5_conn)

    with pytest.raises(ValueError, match="Unknown period '3d'"):
        await service.get_candles("EURUSDm", "3d", _FROM, _TO)

    mock_mt5_conn.run.assert_not_called()


# ---------------------------------------------------------------------------
# Timezone / UTC conversion
# ---------------------------------------------------------------------------


def test_to_utc_timestamp_aware_utc() -> None:
    """A UTC-aware datetime must produce the correct Unix timestamp."""
    dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert _to_utc_timestamp(dt) == int(dt.timestamp())


def test_to_utc_timestamp_aware_gmt_minus_5() -> None:
    """A GMT-5-aware datetime must be converted to its UTC equivalent."""
    gmt_minus_5 = timezone(timedelta(hours=-5))
    dt_local = datetime(2026, 1, 1, 0, 0, 0, tzinfo=gmt_minus_5)   # midnight Ecuador
    dt_utc = datetime(2026, 1, 1, 5, 0, 0, tzinfo=timezone.utc)    # 05:00 UTC

    assert _to_utc_timestamp(dt_local) == _to_utc_timestamp(dt_utc)


def test_to_utc_timestamp_naive_treated_as_utc() -> None:
    """A naive datetime must be treated as UTC, not as local time."""
    naive = datetime(2026, 1, 1, 0, 0, 0)
    aware_utc = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    assert _to_utc_timestamp(naive) == _to_utc_timestamp(aware_utc)



@pytest.mark.asyncio
async def test_get_candles_unknown_symbol(mock_mt5_conn: MagicMock) -> None:
    """symbol_info() returning None must raise MT5SymbolError."""
    # symbol_info() returns None → unknown symbol
    mock_mt5_conn.run = AsyncMock(return_value=None)
    service = CandleService(mock_mt5_conn)

    with pytest.raises(MT5SymbolError):
        await service.get_candles("FAKESYM", "1h", _FROM, _TO)


@pytest.mark.asyncio
async def test_get_candles_empty_result(mock_mt5_conn: MagicMock) -> None:
    """copy_rates_range returning None must raise MT5ConnectionError."""
    from mt5_bridge.exceptions.mt5_exceptions import MT5ConnectionError

    symbol_info_mock = MagicMock()
    mock_mt5_conn.run = AsyncMock(side_effect=[symbol_info_mock, None])

    with patch_last_error():
        service = CandleService(mock_mt5_conn)
        with pytest.raises(MT5ConnectionError):
            await service.get_candles("EURUSDm", "1h", _FROM, _TO)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def patch_last_error(code: int = -4, desc: str = "No data"):
    """Patch mt5.last_error() for tests that exercise error-handling paths."""
    with patch("MetaTrader5.last_error", return_value=(code, desc)):
        yield
