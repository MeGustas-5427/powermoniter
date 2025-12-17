"""死信仓储封装。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async
from django.db import close_old_connections, connections
from django.db.utils import OperationalError

from apps.repositories.models import DeadLetter, Device


class DeadLetterRepository:
    """对 DeadLetter 提供查询与导出能力。"""

    async def create_dead_letter(
        self,
        *,
        device: Optional[Device],
        mac: Optional[str],
        raw_payload: Dict[str, Any],
        reason: str,
        retryable: bool = False,
        meta: Optional[Dict[str, Any]] = None,
    ) -> DeadLetter:
        def _create() -> DeadLetter:
            close_old_connections()
            try:
                return DeadLetter.objects.create(
                    device=device,
                    mac=mac,
                    raw_payload=raw_payload,
                    failure_reason=reason,
                    retryable=retryable,
                    meta=meta,
                )
            except OperationalError:
                connections["default"].close()
                close_old_connections()
                return DeadLetter.objects.create(
                    device=device,
                    mac=mac,
                    raw_payload=raw_payload,
                    failure_reason=reason,
                    retryable=retryable,
                    meta=meta,
                )

        # 避免使用 acreate()，直接将同步 ORM 操作丢到线程池，防止 CurrentThreadExecutor 缺失。
        return await sync_to_async(_create, thread_sensitive=False)()

    async def list_dead_letters(
        self,
        *,
        mac: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        from_ts: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        records = await self._get_dead_letters_sync(mac, from_ts, limit, offset)
        return [self._serialize(record) for record in records]

    @sync_to_async
    def _get_dead_letters_sync(self, mac, from_ts, limit, offset):
        qs = DeadLetter.objects.order_by("-occured_at")
        if mac:
            qs = qs.filter(mac=mac)
        if from_ts:
            qs = qs.filter(occured_at__gte=from_ts)
        return list(qs[offset: offset + limit])

    async def export_samples(self, target: str, limit: int) -> List[Dict[str, Any]]:
        if target not in {"dead_letters", "duplicates"}:
            raise ValueError("不支持的导出目标")
        if target == "dead_letters":
            records = await self.get_recent_dead_letters(limit)
            return [self._serialize(record) for record in records]
        # 当前重复数据仅通过指标暴露，此处返回空列表
        return []

    @sync_to_async
    def get_recent_dead_letters(self, limit):
        return list(
            DeadLetter.objects.order_by("-occured_at")[:limit]
        )

    @staticmethod
    def _serialize(record: DeadLetter) -> Dict[str, Any]:
        return {
            "id": record.id,
            "mac": record.mac,
            "failure_reason": record.failure_reason,
            "occured_at": record.occured_at.isoformat() if record.occured_at else None,
            "retryable": record.retryable,
            "payload": record.raw_payload,
            "meta": record.meta,
        }
