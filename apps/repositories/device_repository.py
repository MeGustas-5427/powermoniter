"""设备仓储层，封装对 Device 模型的操作。"""

from __future__ import annotations

from typing import Iterable, Optional

from asgiref.sync import sync_to_async

from apps.repositories.models import Device, DeviceStatus, IngressType

_UNSET = object()


class DeviceRepository:
    """提供设备增删改查接口。"""

    @staticmethod
    async def create_device(
        *,
        mac: str,
        status: DeviceStatus,
        collect_enabled: bool,
        ingress_type: IngressType,
        ingress_config: dict,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Device:
        config = ingress_config or {}

        if await Device.objects.filter(mac=mac).aexists():
            raise ValueError("MAC 已存在")

        device = await Device.objects.acreate(
            name=config.get("name", mac),
            location=config.get("location", ""),
            mac=mac,
            status=status,
            collect_enabled=collect_enabled,
            ingress_type=ingress_type,
            description=description,
            broker=config.get("broker", ""),
            port=int(config.get("port", 0) or 0),
            pub_topic=config.get("pub_topic", ""),
            sub_topic=config.get("topic") or config.get("sub_topic", ""),
            client_id=config.get("client_id", ""),
            username=config.get("username", ""),
            password=config.get("password", ""),
            user_id=user_id,
        )
        device.ingress_config = config
        return device

    @staticmethod
    async def list_devices(status: Optional[DeviceStatus] = None) -> Iterable[Device]:
        if status is not None:
            return await sync_to_async(lambda: list(Device.objects.filter(status=status)))()
        return await sync_to_async(Device.objects.all)()

    @staticmethod
    async def get_by_mac(mac: str) -> Optional[Device]:
        try:
            await Device.objects.aget(mac=mac)
        except Device.DoesNotExist:
            return None

    @staticmethod
    async def update_device(
        mac: str,
        *,
        status: Optional[DeviceStatus] = None,
        collect_enabled: Optional[bool] = None,
        ingress_type: Optional[IngressType] = None,
        ingress_config: Optional[dict] = None,
        description: Optional[str] = None,
        user_id=_UNSET,
    ) -> Optional[Device]:
        try:
            device = await Device.objects.aget(mac=mac)
        except Device.DoesNotExist:
            return None
        if status is not None:
            device.status = status
        if collect_enabled is not None:
            device.collect_enabled = collect_enabled
        if ingress_type is not None:
            device.ingress_type = ingress_type
        if ingress_config is not None:
            config = ingress_config or {}
            device.ingress_config = config
            device.broker = config.get("broker", device.broker)
            device.port = int(config.get("port", device.port or 0) or 0)
            device.pub_topic = config.get("pub_topic", device.pub_topic)
            device.sub_topic = config.get("topic", device.sub_topic)
            device.client_id = config.get("client_id", device.client_id)
            device.username = config.get("username", device.username)
            device.password = config.get("password", device.password)
        if description is not None:
            device.description = description
        if user_id is not _UNSET:
            device.user_id = user_id
        await device.asave()
        return device
