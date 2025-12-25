"""
ASGI config for powermoniter project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'powermoniter.settings')

django_asgi_app = get_asgi_application()

from apps.services.subscription_manager import subscription_manager
import logging

logger = logging.getLogger(__name__)

"""
启动时查询数据库并选择性订阅
  - powermoniter/asgi.py 的 LifespanApplication 会处理 ASGI 的 lifespan.startup 事件。
  - 收到 lifespan.startup 时，它会执行 subscription_manager.startup()。
  - 所以“自动启动”不是框架本身，而是你在 LifespanApplication 里手动调用了它。
    路径：powermoniter/asgi.py

  是否会启动时查询数据库并选择性订阅

  - 会。在 subscription_manager.startup() 里调用 _get_enabled_devices()。
  - _get_enabled_devices() 只取 status=ENABLED 且 collect_enabled=True 的设备：
      - 代码：Device.objects.filter(status=status, collect_enabled=True)
  - 然后对每个设备执行 start_for_device()，创建任务并连接/订阅。
    路径：apps/services/subscription_manager.py

  补充说明

  - 这个行为是“进程级别”的：如果你用多 worker（多进程）启动，每个进程都会执行一次启动逻辑。
  - 在单进程内通过 _started 避免重复触发（LifespanApplication 里有 _started 标记）。
"""
class LifespanApplication:
    """
    ASGI “包装器”，专门拦截 scope["type"] == "lifespan"（进程启动/退出事件），
    把其它请求（HTTP/WebSocket）原样交给 Django 原生 ASGI app。
    """
    def __init__(self, app):
        self.app = app  # 保存下游 app（Django 的 ASGI app 或 staticfiles handler）
        self._started = False  # 记录是否已执行过 startup，防止重复启动（例如某些情况下lifespan.startup 被触发多次）。

    async def __call__(self, scope, receive, send):
        """ASGI 规定入口：每次有新 scope（lifespan/http/websocket）都会调用这里。"""
        if scope["type"] == "lifespan":  #  判断当前是不是“生命周期”scope（不是请求，是进程级别事件）。
            await self._handle_lifespan(receive, send)  # 如果是 lifespan，就交给专门的处理函数；注意lifespan scope 不需要 scope 本身就能工作，所以这里只传 receive/send。
            return
        await self.app(scope, receive, send)  # 非 lifespan（如 http/websocket）则完全透传给下游app。

    async def _handle_lifespan(self, receive, send):
        """专门处理 ASGI lifespan 协议：从 receive() 收事件、用 send() 回应 complete/failed。"""
        while True:  # lifespan 是“消息流”，需要循环不断接收事件直到 shutdown 完成并返回。
            message = await receive()  # 等待 server（uvicorn）发来的 lifespan 消息，典型是 lifespan.startup 和 lifespan.shutdown。

            if message["type"] == "lifespan.startup":  # 处理启动事件：uvicorn 在开始接收请求前会发这个。
                if not self._started:  # 若此前没启动过，才真正执行一次启动逻辑。
                    try:  # 启动逻辑用 try/except 包住，失败要通知 uvicorn（否则 uvicorn 会一直等）。
                        await subscription_manager.startup()  # 你的“启动时自动订阅所有设备”的核心入口：在进程启动阶段就把订阅任务建起来。
                        self._started = True  # 标记启动成功，后续再收到 startup 不会重复订阅。
                    except Exception as exc:  # 启动过程中任何异常都视为启动失败。
                        # 打日志（带堆栈）。这里 exc_info=exc 属于冗余写法，但效果等同于记录当前 except 的堆栈。
                        logger.exception("Subscription manager startup failed.", exc_info=exc)
                        # 按 ASGI 协议通知uvicorn：启动失败；uvicorn 通常会退出进程。
                        await send({"type": "lifespan.startup.failed", "message": str(exc)})
                        return
                # 启动成功或已启动过，都必须回这个；否则 uvicorn 会一直卡在启动阶段不对外服务。
                await send({"type": "lifespan.startup.complete"})
                continue  # startup 处理完回到循环，继续等待 shutdown。

            if message["type"] == "lifespan.shutdown":  # 处理退出事件：uvicorn 收到停止信号会发这个。
                try:  # shutdown 也包 try/except；失败要回 shutdown.failed。
                    if self._started:  # 只有确实启动过才执行 shutdown；否则直接回 complete（保持幂等）。
                        await subscription_manager.shutdown()  # 你的“停止订阅/取消任务”的核心入口。
                except Exception as exc:  # 关闭过程中异常也要按协议通知。
                    logger.exception("Subscription manager shutdown failed.", exc_info=exc) # 记录 shutdown 异常堆栈。
                    await send({"type": "lifespan.shutdown.failed", "message": str(exc)}) # 按协议通知 shutdown 失败。
                    return  # shutdown 失败后退出 handler。
                await send({"type": "lifespan.shutdown.complete"})  # 告诉 uvicorn：清理结束，可以退出。
                return  # shutdown complete 后结束 lifespan handler（正常结束）。
            # 如果收到了未知 lifespan 消息，只警告并继续循环（不崩）。
            logger.warning("Unknown lifespan message: %s", message.get("type"))

if settings.DEBUG:
    application = ASGIStaticFilesHandler(django_asgi_app)
else:
    application = django_asgi_app

application = LifespanApplication(application)
