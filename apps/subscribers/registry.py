"""订阅器注册表，管理激活状态与指标上报。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from apps.repositories.models import Device, DeviceStatus, IngressType
from apps.telemetry.metrics import (
    DUPLICATE_COUNTER,
    DEAD_LETTER_COUNTER,
    COMMIT_COUNTER,
    INGRESS_COUNTER,
    set_active_subscribers,
    mark_reconnect,
    mark_retry,
    set_lag,
)
from .retry import RetryPolicy

logger = logging.getLogger(__name__)

@dataclass
class SubscriberRecord:
    """记录订阅状态。"""

    device: Device
    last_seen: Optional[float] = None
    lag_seconds: float = 0.0
    status: DeviceStatus = field(init=False)

    def __post_init__(self) -> None:
        self.status = self.device.status


class SubscriberRegistry:
    """维护当前活跃的订阅集合，负责指标同步。"""

    def __init__(self, retry_policy: Optional[RetryPolicy] = None) -> None:
        self._records: Dict[str, SubscriberRecord] = {}
        self._retry_policy = retry_policy or RetryPolicy()
        self._lock = asyncio.Lock()

    async def activate(self, device: Device) -> None:
        """启用设备订阅，并更新指标。"""

        async with self._lock:
            self._records[device.mac] = SubscriberRecord(device=device)
            set_active_subscribers(len(self._records))
        logger.info(f"订阅已激活: {device.mac}-{IngressType.select().get(device.ingress_type)}")

    async def deactivate(self, device: Device) -> None:
        """停用设备订阅。"""

        async with self._lock:
            self._records.pop(device.mac, None)
            set_active_subscribers(len(self._records))
        logger.info(f"订阅已停用: {device.mac}")

    def record_ingress(self, mac: str) -> None:
        """记录入口消息。"""

        INGRESS_COUNTER.labels(mac=mac).inc()

    def record_commit(self, mac: str) -> None:
        """记录成功入库数量。"""

        COMMIT_COUNTER.labels(mac=mac).inc()

    def record_duplicate(self, mac: str) -> None:
        """记录重复数据。"""

        DUPLICATE_COUNTER.labels(mac=mac).inc()

    def record_dead_letter(self, reason: str) -> None:
        """记录死信。"""

        DEAD_LETTER_COUNTER.labels(reason=reason).inc()

    def record_reconnect(self, mac: str) -> None:
        """记录重连事件。"""

        mark_reconnect(mac)

    async def wait_with_retry(self, attempt: int) -> None:
        """根据策略等待下一次重试。"""

        await self._retry_policy.wait_with_retry(attempt)

    def record_retry_failure(self, mac: str, reason: str) -> None:
        """记录重试失败原因。"""

        mark_retry(mac, reason)

    def record_lag(self, mac: str, lag_seconds: float) -> None:
        """记录滞后指标。"""

        set_lag(mac, lag_seconds)

    def snapshot(self) -> Dict[str, Dict[str, object]]:
        """返回当前订阅状态摘要。"""

        return {
            mac: {
                "status": record.device.status,
                "ingress_type": record.device.ingress_type,
                "collect_enabled": getattr(record.device, "collect_enabled", False),
                "lag_seconds": record.lag_seconds,
            }
            for mac, record in self._records.items()
        }


registry = SubscriberRegistry()

