"""定义采集适配器协议，供 MQTT/TCP 实现复用。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Protocol


class Envelope(Protocol):
    """抽象消息载体。"""

    mac: str
    payload: Dict


class SubscriberAdapter(ABC):
    """采集适配器抽象基类。"""

    @abstractmethod
    async def connect(self) -> None:
        """建立连接。"""

    @abstractmethod
    async def listen(self) -> AsyncIterator[Envelope]:
        """监听消息流。"""

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接并清理资源。"""
