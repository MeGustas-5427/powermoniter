"""MQTT 订阅适配器，封装 Paho MQTT 的重连与消费逻辑。

设计目标：
1. 支持鉴权、主题订阅、JSON 负载解析；
2. 连接断开时自动指数退避重连（参照 pub_sub_tcp.py 中的思路）；
3. 对接 `apps.subscribers.registry` 统计指标与死信；
4. 在 FastAPI 生命周期内长期运行，不因主线程结束而退出。

核心流程：
- 调用 `connect()` 后启动 Paho 的网络循环 (`loop_start()`)，并阻塞直至首次连接成功；
- 收到消息在回调线程里解码 JSON，放入异步队列 `_queue`，供 `listen()` 协程消费；
- 断线时异步启动 `_reconnect_loop()`，使用 `RetryPolicy` 控制最大次数与退避间隔；
- 调用 `disconnect()` 时停止自动重连、关闭网络循环并清理指标。
"""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from types import SimpleNamespace
from typing import AsyncIterator, Dict, Optional
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

from apps.telemetry.logging import get_logger
from apps.telemetry.metrics import set_lag
from .base import Envelope, SubscriberAdapter
from apps.subscribers.registry import registry as subscribers_registry
from apps.subscribers.retry import RetryPolicy


def _is_success(reason_code: int | mqtt.ReasonCodes) -> bool:
    """将枚举/整数统一转成布尔：0 表示成功。"""

    return getattr(reason_code, "value", reason_code) == 0


class MQTTAdapter(SubscriberAdapter):
    """长期运行的 MQTT 适配器。

    参数说明：
    - `broker_url`: 形如 `mqtt://user:pass@host:port` 的地址，解析出鉴权与主机信息；
    - `topic`: 订阅主题；
    - `mac`: 统计指标使用的标识；
    - `client_id`: 不传则基于 mac 生成；
    - `keepalive`: MQTT keepalive 秒数；
    - `retry_policy`: 指数退避策略，默认 1→2→4…≤60，最多 12 次。

    运行时会持有：
    - `_client`: Paho MQTT 客户端（线程安全）；
    - `_loop`: 当前 asyncio 事件循环；
    - `_connected`: `Event`，首次连接成功后置位；
    - `_queue`: 异步队列，存放解码后的消息供 `listen()` 消费；
    - `_reconnect_task`: 断线后自动重连的异步任务；
    - `_stop_requested`: 标记停止重连。
    """

    def __init__(
        self,
        *,
        broker_url: str,
        topic: str,
        mac: str,
        client_id: Optional[str] = None,
        keepalive: int = 120,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> None:
        # 解析 broker URL（用户名/密码/主机/端口）
        self._url = urlparse(broker_url)
        self._topic = topic
        self._mac = mac
        self._keepalive = keepalive
        self._policy = retry_policy or RetryPolicy()

        # 运行时上下文：事件循环、连接状态、消息队列、重连任务等
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connected = asyncio.Event()
        self._queue: asyncio.Queue[Envelope] = asyncio.Queue()
        self._stop_requested = False
        self._reconnect_task: Optional[asyncio.Task[None]] = None

        # 日志绑定 mac/topic，方便排查
        self._logger = get_logger("mqtt_adapter", mac=mac, topic=topic)

        # 创建 Paho Client：回调 API 版本使用 v2 以兼容 MQTTv5
        client_id = client_id or f"powermon-{mac}"
        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        # 配置用户名/密码
        if self._url.username:
            self._client.username_pw_set(self._url.username, self._url.password or "")

        # 注册回调
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    # ------------------------------------------------------------------
    # 回调：连接建立 => 订阅主题 + 设置连接事件
    def _on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties=None, *extra) -> None:  # type: ignore[override]
        if _is_success(reason_code) and client.is_connected():
            client.subscribe(self._topic)
            if self._loop:
                # call_soon_threadsafe 需要一个返回 object 的回调，这里用表达式返回 True
                self._loop.call_soon_threadsafe(lambda: (self._connected.set() or True))
            subscribers_registry.record_reconnect(self._mac)
            self._logger.info("MQTT 连接成功")
        else:
            code = getattr(reason_code, "value", reason_code)
            self._logger.warning(f"MQTT 连接失败; code={code}")

    # 回调：断开连接 => 清除连接事件 + 启动重连逻辑
    def _on_disconnect(self, client: mqtt.Client, userdata, reason_code, properties=None, *extra) -> None:  # type: ignore[override]
        code = getattr(reason_code, "value", reason_code)
        self._logger.info(f"MQTT 连接断开; code={code}")
        if self._loop:
            self._loop.call_soon_threadsafe(lambda: (self._connected.clear() or True))
            if not self._stop_requested:
                self._loop.call_soon_threadsafe(self._schedule_reconnect)

    # 回调：收到消息 => 解码 JSON，写入异步队列（供 listen() 消费）
    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            data: Dict[str, object] = json.loads(msg.payload)
        except json.JSONDecodeError:
            subscribers_registry.record_dead_letter("invalid_json")
            self._logger.warning("收到非法 JSON，已记录死信")
            return
        envelope = SimpleNamespace(mac=data.get("mac", self._mac), payload=data)
        if self._loop:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, envelope)
        subscribers_registry.record_ingress(self._mac)

    # ------------------------------------------------------------------
    def _schedule_reconnect(self) -> None:
        """在事件循环中调度重连任务（防止重复创建）。"""

        if not self._loop or self._stop_requested:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """指数退避重连循环，直到成功或超过最大重试次数。"""

        attempt = 1
        while not self._stop_requested:
            try:
                await asyncio.get_running_loop().run_in_executor(None, self._client.reconnect)
                await self._connected.wait()
                self._logger.info("MQTT 重连成功")
                return
            except Exception as exc:  # pragma: no cover - 网络异常路径
                subscribers_registry.record_retry_failure(self._mac, type(exc).__name__)
                self._logger.error(f"MQTT 重连失败 attempt={attempt}, error={exc}")
                if attempt >= self._policy.max_attempts:
                    self._logger.error("超过最大重连次数，停止重试")
                    return
                await self._policy.wait_with_retry(attempt)
                attempt += 1

    # ------------------------------------------------------------------
    async def connect(self) -> None:
        """首次连接：启动 loop_start 并阻塞至连接成功。"""

        self._loop = asyncio.get_running_loop()
        self._stop_requested = False
        host = self._url.hostname or "localhost"
        port = self._url.port or 1883

        self._client.loop_start()  # 单独线程维护网络循环
        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                await self._loop.run_in_executor(None, self._client.connect, host, port, self._keepalive)
                await self._connected.wait()
                return
            except Exception as exc:  # pragma: no cover
                subscribers_registry.record_retry_failure(self._mac, type(exc).__name__)
                self._logger.error(f"MQTT 初始连接失败 attempt={attempt}, error={exc}")
                if attempt >= self._policy.max_attempts:
                    raise ConnectionError(f"MQTT 连接失败，超过最大重试次数") from exc
                await self._policy.wait_with_retry(attempt)

    async def listen(self) -> AsyncIterator[Envelope]:
        """异步消费消息队列，供上层编排。"""

        while True:
            envelope = await self._queue.get()
            yield envelope

    async def disconnect(self) -> None:
        """主动关闭连接：停止重连任务、关闭网络循环并更新指标。"""

        self._stop_requested = True
        if self._reconnect_task:
            self._reconnect_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reconnect_task
        if self._client.is_connected():
            self._client.disconnect()
        self._client.loop_stop()
        set_lag(self._mac, 0.0)
        if self._loop:
            self._loop.call_soon_threadsafe(lambda: (self._connected.clear() or True))


"""
为什么有self._loop、self._connected、self._queue、self._reconnect_task？


• 这些成员是为了把 Paho MQTT（一个同步、依赖线程的客户端）稳稳地“嫁接”到我们
  的异步框架里，让订阅任务能长期运行、支持重连、又能与 asyncio 生态配合。你可
  以把适配器想象成一个「两头都要照顾好」的桥梁：

  ———

  ### 1. self._loop —— 记录当前的 asyncio 事件循环

  - 当我们在 FastAPI 或后台任务里 await adapter.connect() 时，代码运行在某个
    事件循环里（asyncio.get_running_loop()）。
  - Paho 的回调发生在它自己的线程里（loop_start() 会启动一个线程），如果要在
    回调里唤醒 asyncio 的 Event/Queue、创建重连任务，就必须知道主循环是谁、如
    何把任务“派回去”。
  - _loop 由 connect() 捕获，回调里通过 self._loop.call_soon_threadsafe(...)
    安全地把操作交给 asyncio 主线程，避免线程安全问题。

  ———

  ### 2. self._connected —— 表示「已经连上 broker」的事件

  - 首次连接成功时，在 _on_connect() 里 set()；connect() 内会 await
    self._connected.wait()，这样只有当真的连上 MQTT 才返回。
    ↳ 相当于 connect() 替我们做了“阻塞直到成功”的工作。
  - 一旦断线，在 _on_disconnect() 里清掉：_connected.clear()。这让
    _reconnect_loop() 能再次 await self._connected.wait()，直到重连成功。

  ———

  ### 3. self._queue —— 异步消息队列

  - Paho 的 on_message 回调在独立线程里运行，里头不能直接 await。
  - 我们把 msg.payload 解码成字典后，通过
    self._loop.call_soon_threadsafe(self._queue.put_nowait, envelope) 投递到
    队列。
  - 上层可以 async for envelope in adapter.listen(): ...，消费这条异步队
    列，完全不用管 Paho 的线程细节；如果有多个协程同时 listen()，也能发挥
    asyncio.Queue 的并发优势。

  ———

  ### 4. self._reconnect_task —— 异步重连任务（指数退避）

  - 当 _on_disconnect() 触发时我们调用 _schedule_reconnect()，它会在 asyncio
    里启动一个 _reconnect_loop() 协程。
  - 这个协程按照 RetryPolicy 设定的最大次数 & 延迟去调用
    self._client.reconnect()，成功则退出，失败则延长等待时间并重试。
  - self._reconnect_task 用来记录/取消这个重连协程：如果用户主动调用
    disconnect()，就会 cancel() 它，避免重连逻辑还在后台运行。

  ———

  ### 为什么要一起用？

  - self._loop & call_soon_threadsafe：让不同线程安全互动。
  - self._connected：提供“连接状态”这一关键信号，connect() /
    _reconnect_loop() 都依赖它。
  - self._queue：让消息消费变成标准 asyncio 模式，上层调用简单。
  - self._reconnect_task：负责维护重连的生命周期，避免重复启动或无法取消。

  这四个成员组合起来，就像一个小型的状态机：
  连接 → 监听消息 → （若断开）启动重连 → （成功后）恢复监听。
  而上层只需关心订阅消费，对内部线程、事件、队列的细节可以“传闻不管”，这正是
  适配器存在的意义。
"""
