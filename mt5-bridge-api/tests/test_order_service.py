"""Unit tests for OrderService: open, duplicate guard, close, modify."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mt5_bridge.exceptions.mt5_exceptions import MT5OrderError, OrderNotFoundError
from mt5_bridge.models.schemas.order import ModifyOrderRequest, OpenOrderRequest
from mt5_bridge.services.order_service import OrderService


def _make_mt5_result(retcode: int = 10009, order: int = 111222333) -> MagicMock:
    """Build a minimal MT5 TradeResult mock with TRADE_RETCODE_DONE."""
    result = MagicMock()
    result.retcode = retcode
    result.order = order
    result.deal = 444555666
    result.price = 1.10650
    result.volume = 0.10
    result.bid = 1.10640
    result.ask = 1.10660
    result.comment = "Request executed"
    return result


def _make_tick(bid: float = 1.10640, ask: float = 1.10660) -> MagicMock:
    tick = MagicMock()
    tick.bid = bid
    tick.ask = ask
    return tick


# ---------------------------------------------------------------------------
# open_order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_order_success(mock_mt5_conn: MagicMock, db_session) -> None:
    """A brand-new order should be persisted and return is_duplicate=False."""
    tick = _make_tick()
    mt5_result = _make_mt5_result()
    # First run() call → symbol_info_tick (price); second → order_send
    mock_mt5_conn.run = AsyncMock(side_effect=[tick, mt5_result])

    service = OrderService(mock_mt5_conn, db_session)
    request = OpenOrderRequest(
        order_id=uuid.uuid4(),
        symbol="EURUSDm",
        action="BUY",
        order_type="MARKET",
        volume=0.10,
        sl=1.09500,
        tp=1.11500,
        magic=12345,
    )

    response = await service.open_order(request)

    assert response.is_duplicate is False
    assert response.status == "FILLED"
    assert response.broker_ticket == 111222333
    assert response.fill_price == pytest.approx(1.10650)


@pytest.mark.asyncio
async def test_open_order_duplicate(mock_mt5_conn: MagicMock, db_session) -> None:
    """Sending the same order_id twice must return is_duplicate=True on the second call."""
    tick = _make_tick()
    mt5_result = _make_mt5_result()
    mock_mt5_conn.run = AsyncMock(side_effect=[tick, mt5_result])

    service = OrderService(mock_mt5_conn, db_session)
    order_id = uuid.uuid4()
    request = OpenOrderRequest(
        order_id=order_id,
        symbol="EURUSDm",
        action="BUY",
        order_type="MARKET",
        volume=0.10,
    )

    first = await service.open_order(request)
    assert first.is_duplicate is False

    # Reset mock — the second call must NOT reach MT5.
    mock_mt5_conn.run = AsyncMock()
    second = await service.open_order(request)

    assert second.is_duplicate is True
    assert second.order_id == order_id
    mock_mt5_conn.run.assert_not_called()


@pytest.mark.asyncio
async def test_open_order_mt5_rejection(mock_mt5_conn: MagicMock, db_session) -> None:
    """An MT5 retcode other than DONE must raise MT5OrderError."""
    tick = _make_tick()
    rejected_result = _make_mt5_result(retcode=10006)  # TRADE_RETCODE_REJECT
    rejected_result.comment = "Rejected by dealer"
    mock_mt5_conn.run = AsyncMock(side_effect=[tick, rejected_result])

    service = OrderService(mock_mt5_conn, db_session)
    request = OpenOrderRequest(
        order_id=uuid.uuid4(),
        symbol="EURUSDm",
        action="BUY",
        order_type="MARKET",
        volume=0.10,
    )

    with pytest.raises(MT5OrderError):
        await service.open_order(request)


# ---------------------------------------------------------------------------
# close_order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_order_not_found(mock_mt5_conn: MagicMock, db_session) -> None:
    """close_order with an unknown order_id must raise OrderNotFoundError."""
    service = OrderService(mock_mt5_conn, db_session)

    with pytest.raises(OrderNotFoundError):
        await service.close_order(uuid.uuid4())


@pytest.mark.asyncio
async def test_close_order_already_closed(mock_mt5_conn: MagicMock, db_session) -> None:
    """If MT5 returns no open position, the order is marked CLOSED without an MT5 call."""
    # First open the order so it exists in DB.
    tick = _make_tick()
    open_result = _make_mt5_result(order=777888999)
    mock_mt5_conn.run = AsyncMock(side_effect=[tick, open_result])

    service = OrderService(mock_mt5_conn, db_session)
    order_id = uuid.uuid4()
    await service.open_order(
        OpenOrderRequest(
            order_id=order_id, symbol="EURUSDm", action="BUY", order_type="MARKET", volume=0.01
        )
    )

    # Now simulate that positions_get returns nothing (already closed externally).
    mock_mt5_conn.run = AsyncMock(return_value=None)
    response = await service.close_order(order_id)

    assert response.status == "CLOSED"


# ---------------------------------------------------------------------------
# modify_order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_order_not_found(mock_mt5_conn: MagicMock, db_session) -> None:
    """modify_order with an unknown order_id must raise OrderNotFoundError."""
    service = OrderService(mock_mt5_conn, db_session)

    with pytest.raises(OrderNotFoundError):
        await service.modify_order(uuid.uuid4(), ModifyOrderRequest(sl=1.09000))
