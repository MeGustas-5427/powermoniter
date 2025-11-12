"""入库服务，负责幂等写入与死信处理。"""

from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from asgiref.sync import sync_to_async
from apps.repositories.models import Device, DeadLetter, Reading
from apps.repositories.dead_letter_repository import DeadLetterRepository
from apps.subscribers.registry import registry as subscribers_registry

logger = logging.getLogger(__name__)
_dead_letter_repository = DeadLetterRepository()


def _hash_payload(payload: Dict[str, Any]) -> str:
    raw = repr(sorted(payload.items())).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def record_reading(
    *,
    device: Device,
    ts,
    energy_kwh: Decimal,
    power: Optional[Decimal],
    voltage: Optional[Decimal],
    current: Optional[Decimal],
    key: Optional[str],
    payload: Dict[str, Any],
) -> None:
    """写入读数，并在重复时计数不抛错。"""

    payload_hash = _hash_payload(payload)

    def _reading_exists() -> bool:
        return Reading.objects.filter(mac=device.mac, ts=ts, payload_hash=payload_hash).exists()

    # 不能直接使用 QuerySet.aexists()/acreate()，否则会依赖当前线程的 CurrentThreadExecutor。
    # 在采集任务这类自维护事件循环的线程里 executor 并不存在，会抛 RuntimeError。
    # 因此改用 sync_to_async(..., thread_sensitive=False) 把 ORM 操作放到共享线程池中执行。
    if await sync_to_async(_reading_exists, thread_sensitive=False)():
        subscribers_registry.record_duplicate(device.mac)
        logger.warning(f"重复数据,跳过: {device.mac}; ts: {ts}")
        return

    def _create_reading() -> Reading:
        return Reading.objects.create(
            device=device,
            mac=device.mac,
            ts=ts,
            energy_kwh=energy_kwh,
            power=power,
            voltage=voltage,
            current=current,
            key=key,
            payload=payload,
            payload_hash=payload_hash,
        )

    await sync_to_async(_create_reading, thread_sensitive=False)()

    subscribers_registry.record_commit(device.mac)


async def record_dead_letter(
    *,
    device: Optional[Device],
    mac: Optional[str],
    payload: Dict[str, Any],
    reason: str,
    retryable: bool = False,
    meta: Optional[Dict[str, Any]] = None,
) -> DeadLetter:
    """写入死信记录并同步指标。"""

    record = await _dead_letter_repository.create_dead_letter(
        device=device,
        mac=mac,
        raw_payload=payload,
        reason=reason,
        retryable=retryable,
        meta=meta,
    )
    subscribers_registry.record_dead_letter(reason)
    return record
