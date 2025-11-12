"""设备采集订阅管理器。

负责根据设备配置启动/停止采集适配器，并将实时数据落盘到 Reading 表。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional, Union, List

from asgiref.sync import sync_to_async

from apps.adapters.base import Envelope, SubscriberAdapter
from apps.adapters.mqtt_adapter import MQTTAdapter
from apps.adapters.tcp_adapter import TCPAdapter
from apps.repositories.models import Device, DeviceStatus, IngressType
from apps.services.ingestion_service import record_dead_letter, record_reading
from apps.subscribers.registry import registry as subscriber_registry
from apps.subscribers.retry import RetryPolicy

logger = logging.getLogger(__name__)

class AdapterFactory:
    """构建采集适配器。"""

    def create(self, device: Device) -> SubscriberAdapter:
        if device.ingress_type == IngressType.MQTT:
            return self._create_mqtt_adapter(device)
        if device.ingress_type == IngressType.TCP:
            return self._create_tcp_adapter(device)
        raise ValueError(f"未知的采集类型: {device.ingress_type}")

    def _create_mqtt_adapter(self, device: Device) -> SubscriberAdapter:
        broker = getattr(device, "broker", None) or device.ingress_config.get("broker")
        port = getattr(device, "port", None) or device.ingress_config.get("port")
        topic = getattr(device, "sub_topic", None) or device.ingress_config.get("topic")
        if not broker or port is None or not topic:
            raise ValueError("MQTT 配置缺失 broker/port/topic")

        username = getattr(device, "username", "") or ""
        password = getattr(device, "password", "") or ""
        auth = ""
        if username:
            auth = f"{username}:{password}@"
        broker_url = f"mqtt://{auth}{broker}:{port}"
        client_id = getattr(device, "client_id", None) or device.ingress_config.get("client_id")

        return MQTTAdapter(
            broker_url=broker_url,
            topic=topic,
            mac=device.mac,
            client_id=client_id or None,
        )

    def _create_tcp_adapter(self, device: Device) -> SubscriberAdapter:
        host = device.ingress_config.get("host") or getattr(device, "broker", None)
        port = device.ingress_config.get("port") or getattr(device, "port", None)
        if not host or port is None:
            raise ValueError("TCP 配置缺失 host/port")
        return TCPAdapter(host=host, port=int(port), mac=device.mac)


class SubscriptionManager:
    """管理采集协程生命周期。"""

    def __init__(self, adapter_factory: Optional[AdapterFactory] = None) -> None:
        self._adapter_factory = adapter_factory or AdapterFactory()
        self._tasks: Dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()
        self._policy = RetryPolicy()

    async def startup(self) -> None:
        """服务启动时扫描已启用设备。"""

        devices = await self._get_enabled_devices(DeviceStatus.ENABLED)
        for device in devices:
            logger.info(f"启动阶段发现已开启采集的设备: {device.mac}-{device.ingress_type}")
            await self.start_for_device(device)

    @sync_to_async
    def _get_enabled_devices(self, status: DeviceStatus) -> List[Device]:
        return list(Device.objects.filter(status=status, collect_enabled=True))

    async def shutdown(self) -> None:
        """停止所有采集任务。"""

        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        logger.info("采集管理器已停止所有任务")

    async def apply_device(self, device: Device) -> None:
        """根据设备状态决定是否采集。"""
        if self._should_collect(device):
            await self.start_for_device(device)
        else:
            await self.stop_for_device(device.mac)

    async def start_for_device(self, device: Device) -> None:
        """启动指定设备的采集任务。"""

        logger.info(f"准备启动采集任务: {device.mac}-{device.ingress_type}")
        await self.stop_for_device(device.mac)
        task = asyncio.create_task(self._run_device(device), name=f"collect-{device.mac}")
        async with self._lock:
            self._tasks[device.mac] = task

    async def stop_for_device(self, mac: str) -> None:
        """停止指定设备的采集任务。"""

        async with self._lock:
            task = self._tasks.pop(mac, None)
        if task:
            logger.info(f"停止采集任务: {mac}")
            task.cancel()
            with suppress(asyncio.CancelledError):
                """suppress 是 Python 标准库 contextlib 里的一个上下文管理器(context manager),
                作用是捕获并忽略指定类型的异常。简单理解：让某些错误安静地忽略掉，不用写 try/except。"""
                await task

    def _should_collect(self, device: Device) -> bool:
        return device.status == DeviceStatus.ENABLED and bool(device.collect_enabled)

    async def _run_device(self, device: Device) -> None:
        attempt = 0
        create_attempt = 0
        while True:
            # 不能使用 device.arefresh_from_db()，否则会依赖当前线程的 CurrentThreadExecutor，
            # 在 admin 中通过 async_to_sync 调用时 executor 已经关闭会抛 RuntimeError。
            # 改用 sync_to_async + thread_sensitive=False 让刷新操作跑在独立线程池里，避免阻塞和崩溃。
            await sync_to_async(device.refresh_from_db, thread_sensitive=False)()
            if not self._should_collect(device):
                return
            try:
                adapter = self._adapter_factory.create(device)
                logger.info(f"适配器创建成功: {device.mac}-{device.ingress_type}")
            except Exception as exc:
                create_attempt += 1
                logger.error(f"创建适配器失败: {device.mac}; attempt: {create_attempt}", exc_info=exc)
                try:
                    await self._policy.wait_with_retry(create_attempt)
                except RuntimeError:
                    logger.error(f"多次创建适配器失败，停止重试: {device.mac}")
                    await self.stop_for_device(device.mac)
                    return
                continue

            create_attempt = 0

            try:
                await adapter.connect()
                logger.info(f"采集连接建立完成: {device.mac}")
                await subscriber_registry.activate(device)
                async for envelope in adapter.listen():
                    await self._handle_envelope(device, envelope)
                    attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - 运行时保护
                attempt += 1
                logger.error(f"采集任务异常: {device.mac}; attempt: {attempt}", exc_info=exc)
                try:
                    await self._policy.wait_with_retry(attempt)
                except RuntimeError:
                    logger.error(f"采集任务持续失败，停止重试: {device.mac}")
                    await self.stop_for_device(device.mac)
                    return
                continue

            finally:
                with suppress(Exception):
                    await adapter.disconnect()
                await subscriber_registry.deactivate(device)
                logger.info(f"采集任务已清理: {device.mac}")
            await asyncio.sleep(1)

    async def _handle_envelope(self, device: Device, envelope: Envelope) -> None:
        payload = dict(envelope.payload or {})
        mac = payload.get("mac") or device.mac
        subscriber_registry.record_ingress(mac)

        try:
            ts = self._parse_timestamp(payload)
            energy = self._to_decimal(payload.get("energy"))
            if energy is None:
                raise ValueError("missing energy")
            power = self._to_decimal(payload.get("power"))
            voltage = self._to_decimal(payload.get("voltage"))
            current = self._to_decimal(payload.get("current"))
            key = payload.get("key")

            await record_reading(
                device=device,
                ts=ts,
                energy_kwh=energy,
                power=power,
                voltage=voltage,
                current=current,
                key=key,
                payload=payload,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await record_dead_letter(
                device=device,
                mac=mac,
                payload=payload,
                reason=f"ingest_error:{type(exc).__name__}",
                retryable=False,
            )
            logger.warning(f"读数解析失败，已写入死信: {device.mac}", exc_info=exc)

    def _parse_timestamp(self, payload: Dict[str, Union[str, int, float]]) -> datetime:
        raw = payload.get("ts") or payload.get("timestamp")
        if raw is None:
            return datetime.now(timezone.utc)
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        if isinstance(raw, str):
            try:
                ts = datetime.fromisoformat(raw)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts.astimezone(timezone.utc)
            except ValueError:
                return datetime.now(timezone.utc)
        return datetime.now(timezone.utc)

    def _to_decimal(self, value: Optional[Union[str, int, float, Decimal]]) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None


subscription_manager = SubscriptionManager()

__all__ = ["subscription_manager", "SubscriptionManager"]
