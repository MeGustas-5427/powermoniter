"""TCP 订阅适配器，按行读取 JSON 消息。"""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from typing import Optional, AsyncGenerator

from ..subscribers.registry import registry as subscribers_registry
from ..telemetry.metrics import set_lag
from ..subscribers.retry import RetryPolicy
from .base import SubscriberAdapter

logger = logging.getLogger(__name__)


class TCPAdapter(SubscriberAdapter):
    """基于 TCP 的订阅实现，支持指数退避重连。"""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        mac: str,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._mac = mac
        self._policy = retry_policy or RetryPolicy()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def connect(self) -> None:
        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
                subscribers_registry.record_reconnect(self._mac)
                logger.info(f"TCP 连接成功: host: {self._host}; port: {self._port}")
                return
            except Exception as exc:  # pragma: no cover - 网络异常路径
                subscribers_registry.record_retry_failure(self._mac, type(exc).__name__)
                await self._policy.wait_with_retry(attempt)
        raise ConnectionError("TCP 连接失败，超过最大重试次数")

    async def listen(self) -> AsyncGenerator[SimpleNamespace, None]:
        if not self._reader:
            raise RuntimeError("连接尚未建立")
        while True:
            line = await self._reader.readline()
            if not line:
                break
            try:
                data = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                subscribers_registry.record_dead_letter("invalid_json")
                continue
            envelope = SimpleNamespace(mac=data.get("mac", self._mac), payload=data)
            subscribers_registry.record_ingress(self._mac)
            yield envelope

    async def disconnect(self) -> None:
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:  # pragma: no cover
                pass
        set_lag(self._mac, 0.0)

