"""ORM model for the exec_reports table."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mt5_bridge.models.db.base import Base


class ExecReport(Base):
    """Append-only audit entry for a single execution event on an order.

    Columns:
        id:         Auto-generated UUID primary key.
        order_id:   Foreign key to order_map.
        event_type: FILLED | REJECTED | SEND_ERROR | CLOSED | MODIFIED.
        data:       Free-form JSONB payload (MT5 result, latency, error messages).
        created_at: Immutable creation timestamp.
    """

    __tablename__ = "exec_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_map.order_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped["OrderMap"] = relationship(  # noqa: F821
        "OrderMap",
        back_populates="exec_reports",
    )
