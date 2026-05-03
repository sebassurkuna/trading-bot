"""Order endpoints — POST / DELETE / PATCH /api/v1/order."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from mt5_bridge.dependencies import get_mt5, get_session
from mt5_bridge.exceptions.mt5_exceptions import (
    MT5ConnectionError,
    MT5OrderError,
    MT5SymbolError,
    OrderNotFoundError,
)
from mt5_bridge.models.schemas.order import (
    CloseOrderResponse,
    ModifyOrderRequest,
    ModifyOrderResponse,
    OpenOrderRequest,
    OpenOrderResponse,
)
from mt5_bridge.services.mt5_connection import MT5Connection
from mt5_bridge.services.order_service import OrderService

router = APIRouter()


def _make_service(
    mt5_conn: MT5Connection = Depends(get_mt5),
    session: AsyncSession = Depends(get_session),
) -> OrderService:
    """Dependency factory that wires MT5Connection + AsyncSession into OrderService."""
    return OrderService(mt5_conn, session)


@router.post(
    "/order",
    response_model=OpenOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new order (idempotent by order_id)",
    description=(
        "Submit a new BUY/SELL order to MetaTrader 5. "
        "If the same `order_id` is submitted again, the original result is returned "
        "with `is_duplicate=true` and HTTP 200 (no double execution)."
    ),
)
async def open_order(
    request: OpenOrderRequest,
    response: Response,
    service: OrderService = Depends(_make_service),
) -> OpenOrderResponse:
    """Open a market, limit, or stop order. Idempotent by order_id."""
    try:
        result = await service.open_order(request)
        # Downgrade to HTTP 200 when returning a cached duplicate result.
        if result.is_duplicate:
            response.status_code = status.HTTP_200_OK
        return result
    except MT5SymbolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except MT5OrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except MT5ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )


@router.delete(
    "/order/{order_id}",
    response_model=CloseOrderResponse,
    summary="Close an open order by its client order_id",
    description="Closes the MT5 position associated with the given client `order_id`.",
)
async def close_order(
    order_id: uuid.UUID,
    service: OrderService = Depends(_make_service),
) -> CloseOrderResponse:
    """Close the MT5 position associated with the given client order_id."""
    try:
        return await service.close_order(order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except MT5OrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except MT5ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )


@router.patch(
    "/order/{order_id}/modify",
    response_model=ModifyOrderResponse,
    summary="Modify the SL/TP of an open order",
    description="Update the stop-loss and/or take-profit of an existing open position.",
)
async def modify_order(
    order_id: uuid.UUID,
    request: ModifyOrderRequest,
    service: OrderService = Depends(_make_service),
) -> ModifyOrderResponse:
    """Update stop-loss and/or take-profit of an existing open position."""
    try:
        return await service.modify_order(order_id, request)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except MT5OrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except MT5ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
