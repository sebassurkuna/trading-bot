"""Async repository for order_map and exec_reports tables."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mt5_bridge.models.db.exec_report import ExecReport
from mt5_bridge.models.db.order_map import OrderMap


class OrderRepository:
    """Data-access layer for order persistence.

    All methods are async and operate within an injected `AsyncSession`.
    The session lifecycle (commit / rollback) is managed by the service layer.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_order_id(self, order_id: uuid.UUID) -> Optional[OrderMap]:
        """Return an order by its client UUID, or None if not found.

        Args:
            order_id: Client-side UUID.

        Returns:
            The matching OrderMap row, or None.
        """
        result = await self._session.execute(
            select(OrderMap).where(OrderMap.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def create(self, order_id: uuid.UUID, **fields) -> OrderMap:
        """Insert a new row into order_map and flush it to the session.

        Args:
            order_id: Client UUID to use as the primary key.
            **fields: Column keyword arguments (symbol, action, volume, etc.).

        Returns:
            The newly created and flushed OrderMap instance.
        """
        record = OrderMap(order_id=order_id, **fields)
        self._session.add(record)
        await self._session.flush()
        return record

    async def update(self, order_id: uuid.UUID, **fields) -> Optional[OrderMap]:
        """Update one or more columns on an existing order_map row.

        Args:
            order_id: Target order UUID.
            **fields: Column name → new value pairs.

        Returns:
            Updated OrderMap instance, or None if the order was not found.
        """
        record = await self.get_by_order_id(order_id)
        if record is None:
            return None

        for key, value in fields.items():
            setattr(record, key, value)

        await self._session.flush()
        return record

    async def append_exec_report(
        self,
        order_id: uuid.UUID,
        event_type: str,
        data: dict,
    ) -> ExecReport:
        """Append an execution event to exec_reports.

        Args:
            order_id:   Parent order UUID.
            event_type: Label such as 'FILLED', 'REJECTED', 'CLOSED', etc.
            data:       Free-form payload stored as JSONB.

        Returns:
            The persisted ExecReport instance.
        """
        report = ExecReport(
            id=uuid.uuid4(),
            order_id=order_id,
            event_type=event_type,
            data=data,
        )
        self._session.add(report)
        await self._session.flush()
        return report
