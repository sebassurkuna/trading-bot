"""Order service: open, close, modify MT5 positions with idempotency guard."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import MetaTrader5 as mt5
from sqlalchemy.ext.asyncio import AsyncSession

from mt5_bridge.exceptions.mt5_exceptions import (
    MT5OrderError,
    MT5SymbolError,
    OrderNotFoundError,
)
from mt5_bridge.metrics.prometheus import (
    DUPLICATE_ORDER_ATTEMPTS,
    ORDER_LATENCY,
    ORDER_OUTCOME,
)
from mt5_bridge.models.schemas.order import (
    CloseOrderResponse,
    ModifyOrderRequest,
    ModifyOrderResponse,
    OpenOrderRequest,
    OpenOrderResponse,
)
from mt5_bridge.repositories.order_repository import OrderRepository
from mt5_bridge.services.mt5_connection import MT5Connection

logger = logging.getLogger(__name__)

_MARKET_ORDER_TYPE: dict[str, int] = {
    "BUY": mt5.ORDER_TYPE_BUY,
    "SELL": mt5.ORDER_TYPE_SELL,
}

_PENDING_ORDER_TYPE: dict[str, dict[str, int]] = {
    "LIMIT": {
        "BUY": mt5.ORDER_TYPE_BUY_LIMIT,
        "SELL": mt5.ORDER_TYPE_SELL_LIMIT,
    },
    "STOP": {
        "BUY": mt5.ORDER_TYPE_BUY_STOP,
        "SELL": mt5.ORDER_TYPE_SELL_STOP,
    },
}


class OrderService:
    """Handles MT5 order lifecycle with idempotency guard."""

    def __init__(self, connection: MT5Connection, session: AsyncSession) -> None:
        self._conn = connection
        self._session = session
        self._repo = OrderRepository(session)

    async def open_order(self, request: OpenOrderRequest) -> OpenOrderResponse:
        """Open a new order or return cached result if already processed."""
        # Idempotency guard
        existing = await self._repo.get_by_order_id(request.order_id)
        if existing is not None:
            DUPLICATE_ORDER_ATTEMPTS.labels(symbol=request.symbol).inc()
            logger.info("Duplicate order detected: order_id=%s", request.order_id)
            return OpenOrderResponse(
                order_id=existing.order_id,
                broker_ticket=existing.broker_ticket,
                position_ticket=existing.position_ticket,
                status=existing.status,
                fill_price=float(existing.fill_price) if existing.fill_price is not None else None,
                sl=float(existing.sl) if existing.sl is not None else None,
                tp=float(existing.tp) if existing.tp is not None else None,
                timestamp=existing.updated_at,
                is_duplicate=True,
            )

        # Persist PENDING intent
        await self._repo.create(
            order_id=request.order_id,
            status="PENDING",
            symbol=request.symbol,
            action=request.action,
            volume=request.volume,
            sl=request.sl,
            tp=request.tp,
            comment=request.comment,
            magic=request.magic,
        )
        await self._session.commit()

        selected = await self._conn.run(mt5.symbol_select, request.symbol, True)
        if not selected:
            code, desc = mt5.last_error()
            raise MT5SymbolError(
                f"{request.symbol} — symbol_select() failed (code={code}, desc={desc})"
            )

        # Fetch price and symbol info
        price = await self._get_execution_price(request)
        sym_info = await self._conn.run(mt5.symbol_info, request.symbol)
        sym_filling_mode = sym_info.filling_mode if sym_info else 0
        sym_point = sym_info.point if sym_info else 0.00001

        mt5_request = self._build_open_request(request, price, sym_filling_mode, sym_point)
        logger.info("MT5 request: %s", mt5_request)

        start_ms = time.monotonic() * 1000
        try:
            result = await self._conn.order_send(mt5_request)
        except Exception as exc:
            logger.error("order_send() raised exception: %s", exc)
            await self._handle_order_failure(request.order_id, "SEND_ERROR", {}, str(exc))
            ORDER_OUTCOME.labels(operation="open", outcome="failure").inc()
            raise

        latency_ms = time.monotonic() * 1000 - start_ms
        ORDER_LATENCY.labels(operation="open").observe(latency_ms)
        logger.info(
            "order_send() — retcode=%s order=%s deal=%s",
            result.retcode if result else None,
            result.order if result else None,
            result.deal if result else None,
        )

        # Handle MT5 result
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            retcode = result.retcode if result else None
            code, desc = mt5.last_error()
            comment = result.comment if result else f"last_error: code={code}, {desc}"
            await self._handle_order_failure(
                request.order_id, "REJECTED",
                {"retcode": retcode, "comment": comment}, comment,
            )
            ORDER_OUTCOME.labels(operation="open", outcome="failure").inc()
            raise MT5OrderError(
                f"order_send() failed — retcode={retcode}, comment={comment}",
                retcode=retcode,
            )

        broker_ticket: int = result.order
        fill_price: float = result.price

        # Apply SL/TP via TRADE_ACTION_SLTP (required for Market Execution brokers)
        if request.sl is not None or request.tp is not None:
            sltp_request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": request.symbol,
                "position": broker_ticket,
                "sl": request.sl or 0.0,
                "tp": request.tp or 0.0,
            }
            sltp_result = await self._conn.order_send(sltp_request)
            if sltp_result is None or sltp_result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.warning("SL/TP modification failed (non-fatal): %s", sltp_result)

        await self._repo.update(
            request.order_id,
            status="FILLED",
            broker_ticket=broker_ticket,
            position_ticket=broker_ticket,
            fill_price=fill_price,
        )
        await self._repo.append_exec_report(
            request.order_id,
            event_type="FILLED",
            data={
                "retcode": result.retcode,
                "order": result.order,
                "deal": result.deal,
                "volume": result.volume,
                "price": result.price,
                "bid": result.bid,
                "ask": result.ask,
                "comment": result.comment,
                "latency_ms": round(latency_ms, 2),
            },
        )
        await self._session.commit()

        ORDER_OUTCOME.labels(operation="open", outcome="success").inc()
        logger.info(
            "Order opened: order_id=%s ticket=%s fill=%.5f latency=%.1fms",
            request.order_id, broker_ticket, fill_price, latency_ms,
        )

        updated = await self._repo.get_by_order_id(request.order_id)
        return OpenOrderResponse(
            order_id=updated.order_id,
            broker_ticket=updated.broker_ticket,
            position_ticket=updated.position_ticket,
            status=updated.status,
            fill_price=float(updated.fill_price) if updated.fill_price is not None else None,
            sl=float(updated.sl) if updated.sl is not None else None,
            tp=float(updated.tp) if updated.tp is not None else None,
            timestamp=updated.updated_at,
            is_duplicate=False,
        )

    async def close_order(self, order_id: uuid.UUID) -> CloseOrderResponse:
        """Close the open position associated with a client order_id."""
        record = await self._repo.get_by_order_id(order_id)
        if record is None:
            raise OrderNotFoundError(str(order_id))

        positions = await self._conn.run(mt5.positions_get, ticket=record.position_ticket)

        if not positions:
            if record.status != "CLOSED":
                await self._repo.update(order_id, status="CLOSED")
                await self._session.commit()
            return CloseOrderResponse(
                order_id=order_id,
                broker_ticket=record.broker_ticket,
                status="CLOSED",
                close_price=None,
                profit=None,
                timestamp=datetime.now(tz=timezone.utc),
            )

        position = positions[0]
        close_order_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY

        tick = await self._conn.run(mt5.symbol_info_tick, position.symbol)
        close_price: float = tick.bid if position.type == 0 else tick.ask

        sym_info = await self._conn.run(mt5.symbol_info, position.symbol)
        type_filling = self._resolve_filling_mode(
            sym_info.filling_mode if sym_info else 0,
            is_market_order=True,
        )

        close_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": close_order_type,
            "position": position.ticket,
            "price": close_price,
            "deviation": 20,
            "magic": position.magic,
            "comment": "close",
            "type_filling": type_filling,
        }

        start_ms = time.monotonic() * 1000
        result = await self._conn.order_send(close_request)
        latency_ms = time.monotonic() * 1000 - start_ms

        ORDER_LATENCY.labels(operation="close").observe(latency_ms)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            retcode = result.retcode if result else None
            comment = result.comment if result else "result is None"
            ORDER_OUTCOME.labels(operation="close", outcome="failure").inc()
            raise MT5OrderError(
                f"Close order failed — retcode={retcode}, comment={comment}",
                retcode=retcode,
            )

        # Fetch closing deal for actual price and profit.
        actual_close_price = result.price or close_price
        profit: Optional[float] = None
        deals = await self._conn.run(mt5.history_deals_get, ticket=result.order)
        if deals:
            closing_deal = next(
                (d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT), None
            )
            if closing_deal:
                profit = closing_deal.profit
                actual_close_price = closing_deal.price

        await self._repo.update(order_id, status="CLOSED")
        await self._repo.append_exec_report(
            order_id,
            event_type="CLOSED",
            data={
                "retcode": result.retcode,
                "order": result.order,
                "deal": result.deal,
                "close_price": actual_close_price,
                "profit": profit,
                "latency_ms": round(latency_ms, 2),
            },
        )
        await self._session.commit()

        ORDER_OUTCOME.labels(operation="close", outcome="success").inc()
        logger.info(
            "Position closed: order_id=%s profit=%.2f latency=%.1fms",
            order_id,
            profit or 0.0,
            latency_ms,
        )

        return CloseOrderResponse(
            order_id=order_id,
            broker_ticket=record.broker_ticket,
            status="CLOSED",
            close_price=actual_close_price,
            profit=profit,
            timestamp=datetime.now(tz=timezone.utc),
        )

    async def modify_order(
        self, order_id: uuid.UUID, request: ModifyOrderRequest
    ) -> ModifyOrderResponse:
        """Modify the SL and/or TP of an open position."""
        record = await self._repo.get_by_order_id(order_id)
        if record is None:
            raise OrderNotFoundError(str(order_id))

        positions = await self._conn.run(mt5.positions_get, ticket=record.position_ticket)
        if not positions:
            raise MT5OrderError(f"No open position for ticket {record.position_ticket}.")

        position = positions[0]
        new_sl: float = request.sl if request.sl is not None else position.sl
        new_tp: float = request.tp if request.tp is not None else position.tp

        modify_request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "sl": new_sl,
            "tp": new_tp,
            "position": position.ticket,
        }

        start_ms = time.monotonic() * 1000
        result = await self._conn.order_send(modify_request)
        latency_ms = time.monotonic() * 1000 - start_ms

        ORDER_LATENCY.labels(operation="modify").observe(latency_ms)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            retcode = result.retcode if result else None
            comment = result.comment if result else "result is None"
            ORDER_OUTCOME.labels(operation="modify", outcome="failure").inc()
            raise MT5OrderError(
                f"Modify order failed — retcode={retcode}, comment={comment}",
                retcode=retcode,
            )

        await self._repo.update(order_id, status="MODIFIED", sl=new_sl, tp=new_tp)
        await self._repo.append_exec_report(
            order_id, event_type="MODIFIED",
            data={"sl": new_sl, "tp": new_tp, "latency_ms": round(latency_ms, 2)},
        )
        await self._session.commit()

        ORDER_OUTCOME.labels(operation="modify", outcome="success").inc()
        logger.info("Order modified: order_id=%s sl=%.5f tp=%.5f", order_id, new_sl, new_tp)

        updated = await self._repo.get_by_order_id(order_id)
        return ModifyOrderResponse(
            order_id=updated.order_id,
            broker_ticket=updated.broker_ticket,
            status=updated.status,
            sl=float(updated.sl) if updated.sl is not None else None,
            tp=float(updated.tp) if updated.tp is not None else None,
            timestamp=updated.updated_at,
        )

    async def _get_execution_price(self, request: OpenOrderRequest) -> float:
        """Return execution price: live tick for MARKET, user-supplied for LIMIT/STOP."""
        if request.order_type == "MARKET":
            tick = await self._conn.run(mt5.symbol_info_tick, request.symbol)
            if tick is None:
                raise MT5SymbolError(request.symbol)
            return tick.ask if request.action == "BUY" else tick.bid
        return request.price  # type: ignore[return-value]

    @staticmethod
    def _resolve_filling_mode(sym_filling_mode: int, is_market_order: bool = True) -> int:
        """Map filling_mode bitmask to ORDER_FILLING constant (IOC preferred for market)."""
        if is_market_order:
            if sym_filling_mode & 2:
                return mt5.ORDER_FILLING_IOC
            if sym_filling_mode & 1:
                return mt5.ORDER_FILLING_FOK
            return mt5.ORDER_FILLING_RETURN
        if sym_filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        if sym_filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def _build_open_request(
        self,
        request: OpenOrderRequest,
        price: float,
        sym_filling_mode: int = 0,
        sym_point: float = 0.00001,
    ) -> dict:
        """Build MT5 trade request dict. SL/TP applied separately for Market Execution."""
        is_market_order = request.order_type == "MARKET"
        if is_market_order:
            action = mt5.TRADE_ACTION_DEAL
            order_type = _MARKET_ORDER_TYPE[request.action]
        else:
            action = mt5.TRADE_ACTION_PENDING
            order_type = _PENDING_ORDER_TYPE[request.order_type][request.action]

        digits = len(str(sym_point).split('.')[-1].rstrip('0')) if sym_point < 1 else 0
        normalized_price = round(price, digits)

        mt5_request: dict = {
            "action": action,
            "symbol": request.symbol,
            "volume": request.volume,
            "type": order_type,
            "price": normalized_price,
            "deviation": request.deviation,
            "type_filling": self._resolve_filling_mode(sym_filling_mode, is_market_order),
        }
        if action == mt5.TRADE_ACTION_PENDING:
            mt5_request["type_time"] = mt5.ORDER_TIME_GTC

        if request.comment:
            mt5_request["comment"] = request.comment
        if request.magic is not None:
            mt5_request["magic"] = request.magic

        return mt5_request

    async def _handle_order_failure(
        self,
        order_id: uuid.UUID,
        event_type: str,
        data: dict,
        error_message: str,
    ) -> None:
        """Set order status to ERROR and append failure exec report."""
        await self._repo.update(order_id, status="ERROR")
        await self._repo.append_exec_report(
            order_id,
            event_type=event_type,
            data={**data, "error": error_message},
        )
        await self._session.commit()
