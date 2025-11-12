"""Dashboard 设备 API 的 Pydantic Schema。"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from ninja import Schema


class DeviceRuntimeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class DeviceStatusFilter(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ALL = "all"

    def matches(self, status: DeviceRuntimeStatus) -> bool:
        if self is DeviceStatusFilter.ALL:
            return True
        return status.value == self.value


class DeviceListItem(Schema):
    device_id: str
    mac: str
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    status: DeviceRuntimeStatus
    last_seen_at: Optional[str] = None


class DeviceListData(Schema):
    page: int
    page_size: int
    total: int
    items: List[DeviceListItem]


class DeviceListResponse(Schema):
    success: Literal[True] = True
    data: DeviceListData


class ElectricityPoint(Schema):
    timestamp: str
    power_kw: float
    energy_kwh: float
    voltage_v: float
    current_a: float


class ElectricitySeries(Schema):
    device_id: str
    start_time: str
    end_time: str
    interval: Literal["pt5m", "pt30m", "pt120m"]
    points: List[ElectricityPoint]


class ElectricityResponse(Schema):
    success: Literal[True] = True
    data: ElectricitySeries


class ApiErrorSchema(Schema):
    success: Literal[False] = False
    error_code: str
    message: str


class DeviceWindow(str, Enum):
    LAST_24H = "24h"
    LAST_7D = "7d"
    LAST_30D = "30d"


__all__ = [
    "ApiErrorSchema",
    "DeviceListItem",
    "DeviceListData",
    "DeviceListResponse",
    "DeviceRuntimeStatus",
    "DeviceStatusFilter",
    "DeviceWindow",
    "ElectricityPoint",
    "ElectricityResponse",
    "ElectricitySeries",
]
