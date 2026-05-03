"""Account info endpoint — GET /api/v1/account."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from mt5_bridge.dependencies import get_mt5
from mt5_bridge.exceptions.mt5_exceptions import MT5ConnectionError
from mt5_bridge.models.schemas.account import AccountInfoResponse
from mt5_bridge.services.account_service import AccountService
from mt5_bridge.services.mt5_connection import MT5Connection

router = APIRouter()


@router.get(
    "/account",
    response_model=AccountInfoResponse,
    summary="Get MT5 account information",
    description="Returns live account details from the connected MetaTrader 5 terminal.",
)
async def get_account(
    mt5_conn: MT5Connection = Depends(get_mt5),
) -> AccountInfoResponse:
    """Return live account details from the connected MT5 terminal."""
    service = AccountService(mt5_conn)
    try:
        return await service.get_account_info()
    except MT5ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
