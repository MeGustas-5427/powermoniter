"""MQTT adapter with a shared connection pool for multi-topic subscriptions."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from dataclasses import dataclass
from types import SimpleNamespace
from typing import AsyncIterator, Dict, Optional
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

from apps.subscribers.registry import registry as subscribers_registry
from apps.subscribers.retry import RetryPolicy
from apps.telemetry.logging import get_logger
from apps.telemetry.metrics import set_lag
from .base import Envelope, SubscriberAdapter


def _is_success(reason_code: int | mqtt.ReasonCodes) -> bool:
    """Paho/MQTT result code helper (0 is success)."""

    return getattr(reason_code, "value", reason_code) == 0


@dataclass(frozen=True)
class MQTTConnectionKey:
    host: str
    port: int
    username: str
    password: str
    client_id: str

    @classmethod
    def from_broker_url(cls, broker_url: str, client_id: str) -> "MQTTConnectionKey":
        url = urlparse(broker_url)
        host = url.hostname
        port = url.port
        if not host or port is None:
            raise ValueError("MQTT broker_url missing host/port")
        username = url.username or ""
        password = url.password or ""
        return cls(host=host, port=port, username=username, password=password, client_id=client_id)


@dataclass
class TopicSubscription:
    mac: str
    queue: asyncio.Queue[Envelope]


class SharedMQTTConnection:
    """Single Paho client shared across multiple topic subscriptions."""

    def __init__(
        self,
        *,
        key: MQTTConnectionKey,
        keepalive: int = 120,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> None:
        self._key = key
        self._keepalive = keepalive
        self._policy = retry_policy or RetryPolicy()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connected = asyncio.Event()
        self._topics: Dict[str, TopicSubscription] = {}
        self._topics_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._reconnect_task: Optional[asyncio.Task[None]] = None
        self._stop_requested = False
        self._loop_running = False

        self._logger = get_logger("mqtt_connection", client_id=key.client_id, broker=key.host, port=key.port)

        self._client = mqtt.Client(
            client_id=key.client_id,
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        if key.username:
            self._client.username_pw_set(key.username, key.password)

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect


    def _on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties=None, *extra) -> None:  # type: ignore[override]
        # _on_connect 只在连接建立成功时触发(首次连接/重连)，不是每次订阅。
        # Paho 回调在后台线程执行，通过 call_soon_threadsafe 切回 asyncio 事件循环。
        # reason_code 为 0 (或 ReasonCodes.value == 0) 表示连接成功。
        if _is_success(reason_code) and client.is_connected():
            if self._loop:
                # 唤醒等待连接完成的协程(ensure_connected 等)。
                self._loop.call_soon_threadsafe(lambda: (self._connected.set() or True))
                # 连接成功后恢复订阅(首次连接或重连)，不会触发新的连接动作。
                self._loop.call_soon_threadsafe(self._schedule_resubscribe)
                # 记录每个 topic/设备的重连指标。
                self._loop.call_soon_threadsafe(self._schedule_reconnect_metrics)
            # 即便 loop 未设置，也记录日志便于排查。
            self._logger.info("MQTT connected")
        else:
            # 连接失败时记录 reason_code 便于诊断。
            code = getattr(reason_code, "value", reason_code)
            self._logger.warning(f"MQTT connect failed; code={code}")

    def _on_disconnect(self, client: mqtt.Client, userdata, reason_code, properties=None, *extra) -> None:  # type: ignore[override]
        code = getattr(reason_code, "value", reason_code)
        self._logger.info(f"MQTT disconnected; code={code}")
        if self._loop:
            self._loop.call_soon_threadsafe(lambda: (self._connected.clear() or True))
            if not self._stop_requested:
                self._loop.call_soon_threadsafe(self._schedule_reconnect)

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            data = json.loads(msg.payload)
        except json.JSONDecodeError:
            subscribers_registry.record_dead_letter("invalid_json")
            self._logger.warning("MQTT invalid JSON payload")
            return
        if not isinstance(data, dict):
            subscribers_registry.record_dead_letter("invalid_json")
            self._logger.warning("MQTT payload is not an object")
            return
        if self._loop:
            self._loop.call_soon_threadsafe(self._dispatch_message, msg.topic, data)

    def _dispatch_message(self, topic: str, payload: Dict[str, object]) -> None:
        asyncio.create_task(self._handle_message(topic, payload))

    async def _handle_message(self, topic: str, payload: Dict[str, object]) -> None:
        async with self._topics_lock:
            subscription = self._topics.get(topic)
        if not subscription:
            subscribers_registry.record_dead_letter("unknown_topic")
            self._logger.warning(f"MQTT message for unmapped topic: {topic}")
            return
        payload_mac = payload.get("mac")
        payload_mac_norm = str(payload_mac).upper() if payload_mac is not None else None
        expected_mac = subscription.mac
        expected_mac_norm = expected_mac.upper()
        if payload_mac_norm != expected_mac_norm:
            subscribers_registry.record_dead_letter("mac_mismatch")
            self._logger.warning(
                f"MQTT mac mismatch: topic={topic} payload_mac={payload_mac} expected={expected_mac}"
            )
            return
        envelope = SimpleNamespace(mac=subscription.mac, payload=payload)
        subscription.queue.put_nowait(envelope)
        subscribers_registry.record_ingress(subscription.mac)

    def _schedule_reconnect(self) -> None:
        if not self._loop or self._stop_requested:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        attempt = 1
        while not self._stop_requested:
            try:
                await asyncio.get_running_loop().run_in_executor(None, self._client.reconnect)
                await self._connected.wait()
                self._logger.info("MQTT reconnected")
                return
            except Exception as exc:  # pragma: no cover
                await self._record_retry_failure(type(exc).__name__)
                self._logger.error(f"MQTT reconnect attempt={attempt}, error={exc}")
                if attempt >= self._policy.max_attempts:
                    self._logger.error("MQTT reconnect max attempts reached")
                    return
                await self._policy.wait_with_retry(attempt)
                attempt += 1

    def _schedule_resubscribe(self) -> None:
        asyncio.create_task(self._resubscribe_all())

    async def _resubscribe_all(self) -> None:
        async with self._topics_lock:
            topics = list(self._topics.keys())
        for topic in topics:
            self._client.subscribe(topic)

    def _schedule_reconnect_metrics(self) -> None:
        asyncio.create_task(self._record_reconnects())

    async def _record_reconnects(self) -> None:
        async with self._topics_lock:
            subscriptions = list(self._topics.values())
        for subscription in subscriptions:
            subscribers_registry.record_reconnect(subscription.mac)

    async def _record_retry_failure(self, reason: str) -> None:
        async with self._topics_lock:
            subscriptions = list(self._topics.values())
        for subscription in subscriptions:
            subscribers_registry.record_retry_failure(subscription.mac, reason)

    async def ensure_connected(self) -> None:
        if self._connected.is_set():
            return
        async with self._connect_lock:
            if self._connected.is_set():
                return
            self._loop = asyncio.get_running_loop()
            self._stop_requested = False
            if not self._loop_running:
                self._client.loop_start()
                self._loop_running = True
            for attempt in range(1, self._policy.max_attempts + 1):
                try:
                    await self._loop.run_in_executor(
                        None,
                        self._client.connect,
                        self._key.host,
                        self._key.port,
                        self._keepalive,
                    )
                    await self._connected.wait()
                    return
                except Exception as exc:  # pragma: no cover
                    await self._record_retry_failure(type(exc).__name__)
                    self._logger.error(f"MQTT connect attempt={attempt}, error={exc}")
                    if attempt >= self._policy.max_attempts:
                        if self._loop_running:
                            self._client.loop_stop()
                            self._loop_running = False
                        raise ConnectionError("MQTT connect failed") from exc
                    await self._policy.wait_with_retry(attempt)

    async def subscribe(self, topic: str, mac: str) -> asyncio.Queue[Envelope]:
        await self.ensure_connected()
        async with self._topics_lock:
            existing = self._topics.get(topic)
            if existing:
                if existing.mac != mac:
                    raise ValueError(f"topic already bound: {topic}")
                return existing.queue
            queue: asyncio.Queue[Envelope] = asyncio.Queue()
            self._topics[topic] = TopicSubscription(mac=mac, queue=queue)
        if self._connected.is_set():
            self._client.subscribe(topic)
        return queue

    async def unsubscribe(self, topic: str, mac: str) -> None:
        async with self._topics_lock:
            existing = self._topics.get(topic)
            if not existing or existing.mac != mac:
                return
            self._topics.pop(topic, None)
            should_disconnect = not self._topics
        if self._connected.is_set():
            self._client.unsubscribe(topic)
        if should_disconnect:
            await self.disconnect()

    async def publish(self, topic: str, payload: Dict[str, object]) -> None:
        await self.ensure_connected()
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        info = self._client.publish(topic, payload=data, qos=0, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError("MQTT publish failed")
        await asyncio.get_running_loop().run_in_executor(None, info.wait_for_publish)
        async with self._topics_lock:
            has_topics = bool(self._topics)
        if not has_topics:
            await self.disconnect()

    async def disconnect(self) -> None:
        self._stop_requested = True
        if self._reconnect_task:
            self._reconnect_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reconnect_task
        if self._client.is_connected():
            self._client.disconnect()
        if self._loop_running:
            self._client.loop_stop()
            self._loop_running = False
        if self._loop:
            self._loop.call_soon_threadsafe(lambda: (self._connected.clear() or True))


class SharedMQTTConnectionPool:
    def __init__(self) -> None:
        self._connections: Dict[MQTTConnectionKey, SharedMQTTConnection] = {}
        self._lock = asyncio.Lock()

    async def _get_connection(self, key: MQTTConnectionKey) -> SharedMQTTConnection:
        async with self._lock:
            connection = self._connections.get(key)
            if connection is None:
                connection = SharedMQTTConnection(key=key)
                self._connections[key] = connection
            return connection

    async def subscribe(self, key: MQTTConnectionKey, topic: str, mac: str) -> asyncio.Queue[Envelope]:
        connection = await self._get_connection(key)
        return await connection.subscribe(topic, mac)

    async def unsubscribe(self, key: MQTTConnectionKey, topic: str, mac: str) -> None:
        connection = await self._get_connection(key)
        await connection.unsubscribe(topic, mac)

    async def publish(self, key: MQTTConnectionKey, topic: str, payload: Dict[str, object]) -> None:
        connection = await self._get_connection(key)
        await connection.publish(topic, payload)

    async def close_all(self) -> None:
        async with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for connection in connections:
            with suppress(Exception):
                await connection.disconnect()


mqtt_pool = SharedMQTTConnectionPool()


class MQTTAdapter(SubscriberAdapter):
    """Adapter for device subscriptions using the shared pool."""

    def __init__(
        self,
        *,
        broker_url: str,
        topic: str,
        mac: str,
        client_id: Optional[str] = None,
    ) -> None:
        if not client_id:
            raise ValueError("MQTT config missing client_id")
        self._topic = topic
        self._mac = mac
        self._client_id = client_id
        self._key = MQTTConnectionKey.from_broker_url(broker_url, self._client_id)
        self._queue: Optional[asyncio.Queue[Envelope]] = None
        self._logger = get_logger("mqtt_adapter", mac=mac, topic=topic)

    async def connect(self) -> None:
        self._queue = await mqtt_pool.subscribe(self._key, self._topic, self._mac)
        self._logger.info("MQTT subscribed")

    async def listen(self) -> AsyncIterator[Envelope]:
        if not self._queue:
            raise RuntimeError("MQTT adapter not connected")
        while True:
            envelope = await self._queue.get()
            yield envelope

    async def disconnect(self) -> None:
        if self._queue:
            await mqtt_pool.unsubscribe(self._key, self._topic, self._mac)
            self._queue = None
        set_lag(self._mac, 0.0)



"""
共享 MQTT 连接说明（单连接多 topic）：

1. SharedMQTTConnection._loop
- Paho 回调在后台线程执行，使用 call_soon_threadsafe 切回 asyncio loop。
- ensure_connected() 获取当前 loop 并等待 _connected。

2. SharedMQTTConnection._connected
- on_connect 置位，on_disconnect 清除。
- connect/reconnect 都等待该事件。

3. SharedMQTTConnection._topics
- topic -> TopicSubscription(mac, queue) 映射。
- 每个 topic 有独立队列；MQTTAdapter.listen 只消费自己的队列。

4. SharedMQTTConnection._reconnect_task
- on_disconnect 且非 stop_requested 时触发重连；disconnect() 时取消。

消息流程:
on_message -> _dispatch_message -> _handle_message:
- 按 topic 归属设备；
- payload mac 不一致则丢弃并记录 dead-letter。

发布:
- mqtt_pool.publish 复用同一连接。
- 若无订阅 topic（仅发布），发布完成后自动断开。
"""

