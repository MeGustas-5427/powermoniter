"""Django admin customisations for repository models."""

from __future__ import annotations

from typing import Any, Dict

from django.contrib import admin
from asgiref.sync import async_to_sync

from .models import DeadLetter, Device, Reading, SubscriptionCheckpoint, User
from apps.services.subscription_manager import subscription_manager


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "is_active", "is_staff", "created_at", "last_login_at")
    search_fields = ("username",)
    list_filter = ("is_active", "is_staff")
    readonly_fields = ("created_at", "last_login_at")
    fieldsets = (
        (None, {"fields": ("username", "password_hash", "is_active", "is_staff")}),
        ("审计", {"classes": ("collapse",), "fields": ("created_at", "last_login_at")}),
    )


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "mac",
        "ingress_type",
        "status",
        "collect_enabled",
        "user",
        "updated_at",
    )
    list_filter = ("ingress_type", "status", "collect_enabled")
    search_fields = ("name", "mac", "location", "description")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "基础信息",
            {
                "fields": (
                    "name",
                    "location",
                    "mac",
                    "user",
                    "description",
                    "status",
                    "collect_enabled",
                )
            },
        ),
        (
            "接入配置",
            {
                "fields": (
                    "ingress_type",
                    "broker",
                    "port",
                    "pub_topic",
                    "sub_topic",
                    "client_id",
                    "username",
                    "password",
                )
            },
        ),
        ("审计", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    def save_model(
        self,
        request: Any,
        obj: Device,
        form: Dict[str, Any],
        change: bool,
    ) -> None:
        """
        • 当你在后台切换某台设备的 collect_enabled 后，整个链路是这样触
          发的：

          1. 后台保存表单 → DeviceAdmin.save_model
             在 admin.py: DeviceAdmin 重写了
             save_model。当你在界面点保存时，FastAdmin 会调用这个方法，它先把变更写回
             device 表，然后读取最新的设备对象，并执行
             await subscription_manager.apply_device(device)

          2. 调度逻辑 → SubscriptionManager.apply_device
             SubscriptionManager 定义在 apps/services/
             subscription_manager.py，它根据 Device.status 和 collect_enabled 判定是
             否需要采集：
             if device.status == DeviceStatus.ENABLED and device.collect_enabled:
                 await start_for_device(device)      # 启动采集协程
             else:
                 await stop_for_device(device.mac)   # 停止采集

          3. 采集协程 & 数据入库
              - 启动时会根据 ingress_type 选择 MQTT 或 TCP 适配器，建立连接并监听消
                息流。
              - 适配器收到的数据结构和 pub_sub_tcp.py 的 on_message 输出一致（包含
                mac、energy、power、voltage、current、key 等字段）。
              - 每获取一条消息，SubscriptionManager 会调用 record_reading（apps/
                services/ingestion_service.py）把读数写入 Reading 表；解析失
                败或缺关键字段的 payload 会落入 DeadLetter。
              - 当你把开关关掉或设备被禁用，会调用 stop_for_device 取消协程并断开连接。

          4. API 同步逻辑
             通过 REST 接口新增/更新设备时（apps/api/routes/devices.py:28-
             84），也同样在落库后调用 subscription_manager.apply_device，保证后台和
             API 的行为一致。

          因此，你在后台点击“开启采集”这一操作，会触发一条完整的“保存 → save_model →
          SubscriptionManager.apply_device → 启动采集 → 写入 Reading”链路，实时把设备
          的采集状态与运行时采集任务联动起来。
        """
        super().save_model(request, obj, form, change)
        async_to_sync(subscription_manager.apply_device)(obj)


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("mac", "ts", "energy_kwh", "power", "voltage", "current")
    search_fields = ("mac",)
    list_filter = ("ts",)
    readonly_fields = ("ingested_at",)


@admin.register(DeadLetter)
class DeadLetterAdmin(admin.ModelAdmin):
    list_display = ("mac", "failure_reason", "occured_at", "retryable")
    search_fields = ("mac", "failure_reason")
    list_filter = ("retryable",)
    readonly_fields = ("occured_at",)


@admin.register(SubscriptionCheckpoint)
class SubscriptionCheckpointAdmin(admin.ModelAdmin):
    list_display = ("device", "mac", "last_envelope_ts", "updated_at")
    search_fields = ("mac", "device__name")
    readonly_fields = ("updated_at",)
