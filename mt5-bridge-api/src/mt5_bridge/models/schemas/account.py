"""Pydantic schema for account info response."""

from __future__ import annotations

from pydantic import BaseModel


class AccountInfoResponse(BaseModel):
    """Response for GET /api/v1/account."""

    account_id: int
    name: str
    broker: str
    currency: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    leverage: int
    is_trade_allowed: bool
    server: str
