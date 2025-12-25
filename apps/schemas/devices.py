"""设备相关的 Pydantic 模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from pydantic import Field, field_validator
from ninja import Schema
from apps.repositories.models import Device, DeviceStatus, IngressType


class DeviceBase(Schema):
    """设备公共字段。"""

    mac: str = Field(..., min_length=12, max_length=12, description="设备 MAC (大写)" )
    status: DeviceStatus = Field(DeviceStatus.ENABLED, description="设备状态")
    collect_enabled: bool = Field(False, description="是否启用数据采集")
    ingress_type: IngressType = Field(IngressType.MQTT, description="采集入口类型")
    ingress_config: Dict[str, Any] = Field(..., description="采集入口配置")
    description: Optional[str] = Field(None, max_length=255, description="备注")

    @field_validator("mac")
    @classmethod
    def _upper_mac(cls, value: str) -> str:
        mac = value.upper()
        if len(mac) != 12:
            raise ValueError("MAC 长度必须为 12")
        return mac


class DeviceCreate(DeviceBase):
    """创建设备请求体。"""

    pass


class DeviceUpdate(Schema):
    """更新设备请求体。"""

    status: Optional[DeviceStatus] = None
    collect_enabled: Optional[bool] = None
    ingress_type: Optional[IngressType] = None
    ingress_config: Optional[Dict[str, Any]] = None
    description: Optional[str] = Field(None, max_length=255)


class DevicePublishPayload(Schema):
    """MQTT publish payload for device settings."""

    timerEnable: int = Field(..., ge=0, le=1, description="Enable timer reporting (0/1)")
    timerInterval: int = Field(..., ge=5, le=86400, description="Timer interval seconds (5-86400)")


class DeviceResponse(DeviceBase):
    """设备响应结构。"""

    created_at: Optional[str] = None

    @classmethod
    def from_model(cls, device: Device) -> "DeviceResponse":
        return cls(
            mac=device.mac,
            status=device.status,
            collect_enabled=device.collect_enabled,
            ingress_type=device.ingress_type,
            ingress_config=device.ingress_config or {},
            description=device.description,
            created_at=device.created_at.isoformat() if device.created_at else None,
        )


class DeviceListResponse(Schema):
    """设备列表响应。"""

    items: List[DeviceResponse]
    page: int = 1
    page_size: int = Field(default=50, ge=1, le=200)
    total: int

class DevicePublishResponse(Schema):
    success: Literal[True] = True

