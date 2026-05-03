"""Pydantic schemas for order request and response payloads."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class OpenOrderRequest(BaseModel):
    """Payload for POST /api/v1/order.

    Attributes:
        order_id:   Client-side UUID v4 used as the idempotency key.
        symbol:     MT5 symbol with broker suffix, e.g. 'EURUSDm'.
        action:     Trade direction: BUY or SELL.
        order_type: Execution type: MARKET, LIMIT, or STOP.
        volume:     Lot size (must be > 0).
        price:      Required for LIMIT / STOP orders; ignored for MARKET.
        sl:         Stop-loss price (optional).
        tp:         Take-profit price (optional).
        comment:    Free-text label forwarded to MT5 (max 64 chars).
        magic:      EA magic number for position identification.
        deviation:  Maximum price deviation in points (default 20).
    """

    order_id: uuid.UUID = Field(..., description="Client-side idempotency key (UUID v4).")
    symbol: str = Field(..., description="MT5 symbol, e.g. 'EURUSDm'.")
    action: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT", "STOP"] = "MARKET"
    volume: float = Field(..., gt=0, description="Lot size.")
    price: Optional[float] = Field(None, description="Required for LIMIT / STOP orders.")
    sl: Optional[float] = Field(None, description="Stop-loss price.")
    tp: Optional[float] = Field(None, description="Take-profit price.")
    comment: Optional[str] = Field(None, max_length=64)
    magic: Optional[int] = Field(None, description="EA magic number.")
    deviation: int = Field(20, ge=0, description="Maximum price deviation in points.")

    @model_validator(mode="after")
    def validate_price_for_pending(self) -> "OpenOrderRequest":
        """Ensure price is provided for LIMIT and STOP orders."""
        if self.order_type in ("LIMIT", "STOP") and self.price is None:
            raise ValueError("'price' is required for LIMIT and STOP orders.")
        return self


class OpenOrderResponse(BaseModel):
    """Response for POST /api/v1/order."""

    order_id: uuid.UUID
    broker_ticket: Optional[int]
    position_ticket: Optional[int]
    status: str
    fill_price: Optional[float]
    sl: Optional[float]
    tp: Optional[float]
    timestamp: datetime
    is_duplicate: bool


class CloseOrderResponse(BaseModel):
    """Response for DELETE /api/v1/order/{orderId}."""

    order_id: uuid.UUID
    broker_ticket: Optional[int]
    status: str
    close_price: Optional[float]
    profit: Optional[float]
    timestamp: datetime


class ModifyOrderRequest(BaseModel):
    """Payload for PATCH /api/v1/order/{orderId}/modify.

    At least one of sl or tp must be provided.
    """

    sl: Optional[float] = Field(None, description="New stop-loss price.")
    tp: Optional[float] = Field(None, description="New take-profit price.")

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "ModifyOrderRequest":
        """Ensure the request modifies at least one of sl or tp."""
        if self.sl is None and self.tp is None:
            raise ValueError("At least one of 'sl' or 'tp' must be provided.")
        return self


class ModifyOrderResponse(BaseModel):
    """Response for PATCH /api/v1/order/{orderId}/modify."""

    order_id: uuid.UUID
    broker_ticket: Optional[int]
    status: str
    sl: Optional[float]
    tp: Optional[float]
    timestamp: datetime
