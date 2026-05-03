"""Aggregates all v1 API routers under the /api/v1 prefix."""

from __future__ import annotations

from fastapi import APIRouter

from mt5_bridge.api.v1 import account, candles, orders

router = APIRouter(prefix="/api/v1")

router.include_router(account.router, tags=["Account"])
router.include_router(orders.router, tags=["Orders"])
router.include_router(candles.router, tags=["Candles"])
