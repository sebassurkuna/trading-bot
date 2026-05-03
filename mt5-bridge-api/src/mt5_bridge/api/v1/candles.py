"""Candles endpoint — GET /api/v1/tick/{symbol}."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from mt5_bridge.dependencies import get_mt5
from mt5_bridge.exceptions.mt5_exceptions import MT5ConnectionError, MT5SymbolError
from mt5_bridge.models.schemas.candle import CandlesResponse
from mt5_bridge.services.candle_service import VALID_PERIODS, CandleService
from mt5_bridge.services.mt5_connection import MT5Connection

router = APIRouter()


@router.get(
    "/tick/{symbol}",
    response_model=CandlesResponse,
    summary="Get historical OHLCV candles",
    description=(
        "Returns historical OHLCV candle data for the requested symbol and period. "
        f"Valid periods: {', '.join(VALID_PERIODS)}."
    ),
)
async def get_candles(
    symbol: str,
    from_: datetime = Query(
        ...,
        alias="from",
        description="Range start (ISO 8601 UTC). Example: 2026-01-01T00:00:00Z",
    ),
    to: datetime = Query(
        ...,
        description="Range end (ISO 8601 UTC). Example: 2026-02-25T00:00:00Z",
    ),
    period: str = Query(
        "1h",
        description=f"Candle period. Valid options: {', '.join(VALID_PERIODS)}.",
    ),
    mt5_conn: MT5Connection = Depends(get_mt5),
) -> CandlesResponse:
    """Return historical OHLCV candles for backtesting."""
    service = CandleService(mt5_conn)
    try:
        return await service.get_candles(symbol, period, from_, to)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except MT5SymbolError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except MT5ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
