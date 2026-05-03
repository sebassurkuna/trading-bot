"""ORM model for the order_map table."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mt5_bridge.models.db.base import Base


class OrderMap(Base):
    """Maps a client-side order_id to an MT5 broker ticket and tracks its lifecycle.

    Columns:
        order_id:        Client-provided UUID (idempotency key).
        broker_ticket:   MT5 order ticket returned by order_send().
        position_ticket: MT5 position ticket (equals broker_ticket on hedging accounts).
        status:          PENDING | FILLED | MODIFIED | CLOSED | ERROR.
        symbol:          MT5 symbol, e.g. 'EURUSDm'.
        action:          BUY or SELL.
        volume:          Lot size.
        fill_price:      Actual execution price.
        sl / tp:         Stop-loss / take-profit prices.
        comment:         Free-text label (passed to MT5).
        magic:           EA magic number.
    """

    __tablename__ = "order_map"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    broker_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    position_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    fill_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    sl: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    tp: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    magic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    exec_reports: Mapped[list["ExecReport"]] = relationship(  # noqa: F821
        "ExecReport",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
