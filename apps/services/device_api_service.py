"""面向 Dashboard 的查询逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Sequence, Any, Literal
from uuid import UUID

from asgiref.sync import sync_to_async
from ninja.pagination import PageNumberPagination
from django.db import connection
from django.db.models import Max

from apps.repositories.models import Device, DeviceStatus, Reading
from apps.schemas.device_api import (
    DeviceListData,
    DeviceListItem,
    DeviceRuntimeStatus,
    DeviceStatusFilter,
    DeviceWindow,
    ElectricityPoint,
    ElectricitySeries,
)


class DeviceNotFoundError(Exception):
    """设备不存在。"""


class InvalidTimeRangeError(Exception):
    """start/end 不满足 24h/7d/30d。"""


@dataclass(frozen=True)
class WindowConfig:
    duration: timedelta
    bucket: timedelta
    interval_label: Literal["pt5m","pt30m","pt120m"]


@dataclass(frozen=True)
class PaginationParams:
    page: int = 1
    size: int = 20


class DeviceApiService:
    """封装设备列表与能耗曲线的查询逻辑。

    设计约定：
    1. 所有输入都转换为 UTC，以保证 bucket 计算一致
    2. 设备列表：一次性查询+本地过滤，避免分页跨状态抖动
    3. 能耗曲线：窗口长度固定 (24h/7d/30d)，并映射为 5m/15m/60m 桶
    4. service 不关心鉴权/响应包装，仅返回 Pydantic Schema 所需数据
    """

    _ONLINE_THRESHOLD = timedelta(minutes=10)
    _WINDOW_CONFIG: Dict[DeviceWindow, WindowConfig] = {
        DeviceWindow.LAST_24H: WindowConfig(duration=timedelta(hours=24), bucket=timedelta(minutes=5), interval_label="pt5m"),
        DeviceWindow.LAST_7D: WindowConfig(duration=timedelta(days=7), bucket=timedelta(minutes=30), interval_label="pt30m"),
        DeviceWindow.LAST_30D: WindowConfig(duration=timedelta(days=30), bucket=timedelta(hours=2), interval_label="pt120m"),
    }

    @classmethod
    async def list_devices(cls, *, user_id: str, status_filter: DeviceStatusFilter, params: PaginationParams) -> DeviceListData:
        """
        查询设备的列表页数据
        :param user_id: 用户uuid
        :param status_filter: 设备状态条件过滤器，根据前端指定的设备状态，譬如：在线状态；返回全部在线状态的设备
        :param params: 分页器
        :return:
        """
        devices = await cls._get_devices_by_user_id(user_id=user_id)
        device_ids = [device.id for device in devices]
        # 预先把所有设备的 last_seen 映射成 dict，避免对单个设备重复 hitting DB
        last_seen_map = await cls._fetch_last_seen(device_ids)
        now = cls._now()

        items: List[DeviceListItem] = []
        for device in devices:
            last_seen = last_seen_map.get(device.id)
            status = cls._determine_status(device, last_seen, now)
            if not status_filter.matches(status):
                continue
            items.append(
                DeviceListItem(
                    device_id=str(device.id),
                    mac=device.mac,
                    name=device.name,
                    description=device.description,
                    location=getattr(device, "location", None),
                    status=status,
                    last_seen_at=cls._format_timestamp(last_seen),
                )
            )

        paginator = PageNumberPagination()
        page = max(1, params.page)
        page_size = max(1, params.size)
        pagination_input = paginator.Input(page=page, page_size=page_size)
        paginated = paginator.paginate_queryset(items, pagination=pagination_input)
        actual_page_size = paginator._get_page_size(pagination_input.page_size)

        return DeviceListData(
            page=pagination_input.page,
            page_size=actual_page_size,
            total=paginated["count"],
            items=list(paginated["items"]),
        )

    @classmethod
    @sync_to_async
    def _get_devices_by_user_id(cls, user_id: str) -> List[Device]:
        return list(Device.objects.filter(user_id=user_id).order_by("name"))

    @classmethod
    async def get_device_electricity(
        cls,
        device_id: UUID,
        *,
        user_id: str,
        window: DeviceWindow,
    ) -> ElectricitySeries:
        """
        按预设窗口(24h/7d/30d)返回用电曲线
        """
        try:
            device = await Device.objects.aget(id=device_id, user_id=user_id)
        except Device.DoesNotExist:
            raise DeviceNotFoundError

        config = cls._WINDOW_CONFIG.get(window)
        if config is None:
            raise InvalidTimeRangeError

        end_utc = cls._now()
        start_utc = end_utc - config.duration
        bucket_seconds = int(config.bucket.total_seconds())
        bucket_count = int(config.duration.total_seconds() // bucket_seconds)

        if connection.vendor == "postgresql":
            buckets = await cls._aggregate_buckets_postgres(
                device_id=device.id,
                start_utc=start_utc,
                end_utc=end_utc,
                bucket_count=bucket_count,
                bucket_seconds=bucket_seconds,
                config=config,
            )
        else:
            readings = await cls._get_readings_by_device_id(device.id, start_utc, end_utc)
            buckets = cls._build_buckets(start_utc, config.bucket, bucket_count, readings)

        points = [
            ElectricityPoint(
                timestamp=cls._format_timestamp(bucket_ts),
                power_kw=bucket_stats["power"],
                energy_kwh=bucket_stats["energy"],
                voltage_v=bucket_stats["voltage"],
                current_a=bucket_stats["current"],
            )
            for bucket_ts, bucket_stats in buckets
            if bucket_stats["count"] > 0
        ]

        return ElectricitySeries(
            device_id=str(device.id),
            start_time=cls._format_timestamp(start_utc),
            end_time=cls._format_timestamp(end_utc),
            interval=config.interval_label,
            points=points,
        )

    @classmethod
    @sync_to_async
    def _get_readings_by_device_id(cls, device_id: str, start_utc, end_utc) -> List[dict[str, Any]]:
        return list(Reading.objects.filter(
            device_id=device_id,
            ts__gte=start_utc,
            ts__lte=end_utc,
        ).order_by("ts").values(
            "ts",
            "energy_kwh",
            "power",
            "voltage",
            "current",
        ))

    @classmethod
    async def _fetch_last_seen(cls, device_ids: Sequence[UUID]) -> Dict[UUID, datetime]:
        """获取设备ids列表每台设备最近一次的时间(ts)"""
        if not device_ids:
            return {}
        rows = (await cls._get_devices_reading_last_seen(device_ids))
        return {
            row["device_id"]: DeviceApiService._ensure_utc(row["last_seen"])
            for row in rows
            if row.get("last_seen") is not None
        }

    @staticmethod
    @sync_to_async
    def _get_devices_reading_last_seen(device_ids) -> List[dict[str, Any]]:
        return list(
            Reading.objects.filter(device_id__in=device_ids)
            .values("device_id")
            .annotate(last_seen=Max("ts"))
        )

    @classmethod
    def _determine_status(
        cls,
        device: Device,
        last_seen: datetime | None,
        now: datetime,
    ) -> DeviceRuntimeStatus:
        """判断设备的状态"""
        if not device.collect_enabled or device.status == DeviceStatus.DISABLED:
            return DeviceRuntimeStatus.MAINTENANCE  # 如果没有允许采集 或者 设备没有打开 则为维护状态
        if last_seen and now - last_seen <= cls._ONLINE_THRESHOLD:
            return DeviceRuntimeStatus.ONLINE  # 如果有最近时间并且距离最近时间少于10分钟 则为在线状态
        return DeviceRuntimeStatus.OFFLINE  # 设备下线

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _format_timestamp(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
    
    @staticmethod
    def _empty_bucket_stats() -> Dict[str, float | int]:
        return {
            "count": 0,
            "power": 0.0,
            "voltage": 0.0,
            "current": 0.0,
            "energy": 0.0,
        }

    @classmethod
    def _build_buckets(
        cls,
        start: datetime,
        bucket: timedelta,
        bucket_count: int,
        readings: Sequence[dict],
    ) -> List[tuple[datetime, Dict[str, object]]]:
        # Step 1: 统一转换到 UTC，确保所有时间戳基准一致
        start = cls._ensure_utc(start)
        bucket_seconds = int(bucket.total_seconds())
        buckets: List[tuple[datetime, Dict[str, float | int | Decimal]]] = []
        # Step 2: 预生成每个桶并初始化累加器，后续循环无需再判空
        for index in range(bucket_count):
            bucket_ts = start + index * bucket
            buckets.append(
                (
                    bucket_ts,
                    {
                        "count": 0,
                        "power": 0.0,
                        "voltage": 0.0,
                        "current": 0.0,
                        "energy": 0.0,
                        "last_power": None,
                        "last_voltage": None,
                        "last_current": None,
                        "first_energy": None,
                        "last_energy": None,
                    },
                )
            )

        # Step 3: 遍历读数，按时间差定位桶下标并记录最新读数/能量边界
        for reading in readings:
            ts = cls._ensure_utc(reading["ts"])
            delta = ts - start
            idx = int(delta.total_seconds() // bucket_seconds)
            if idx < 0 or idx >= len(buckets):
                continue
            bucket_stats = buckets[idx][1]
            bucket_stats["count"] += 1
            bucket_stats["last_power"] = float(reading.get("power") or 0.0)
            bucket_stats["last_voltage"] = float(reading.get("voltage") or 0.0)
            bucket_stats["last_current"] = float(reading.get("current") or 0.0)
            energy_value = Decimal(reading.get("energy_kwh") or 0)
            if bucket_stats["first_energy"] is None:
                bucket_stats["first_energy"] = energy_value
            bucket_stats["last_energy"] = energy_value

        # Step 4: 生成最终点位数据，瞬时值取桶内最新读数，energy 取最后-最初
        for _, stats in buckets:
            count = stats["count"]
            if count:
                stats["power"] = float(stats.get("last_power") or 0.0)
                stats["voltage"] = float(stats.get("last_voltage") or 0.0)
                stats["current"] = float(stats.get("last_current") or 0.0)
                first_energy = stats.get("first_energy")
                last_energy = stats.get("last_energy")
                if first_energy is None or last_energy is None:
                    stats["energy"] = 0.0
                else:
                    delta_energy = last_energy - first_energy
                    stats["energy"] = float(delta_energy) if delta_energy >= 0 else 0.0
            else:
                stats["power"] = stats["voltage"] = stats["current"] = stats["energy"] = 0.0
        return buckets

    @classmethod
    async def _aggregate_buckets_postgres(
        cls,
        *,
        device_id: UUID,
        start_utc: datetime,
        end_utc: datetime,
        bucket_count: int,
        bucket_seconds: int,
        config: WindowConfig,
    ) -> List[tuple[datetime, Dict[str, float | int]]]:
        start_epoch = int(start_utc.replace(tzinfo=timezone.utc).timestamp())
        sql = """
        WITH raw AS (
            SELECT
                floor((extract(epoch FROM ts) - %(start_epoch)s) / %(bucket_seconds)s)::bigint AS bucket_index,
                ts,
                energy_kwh,
                power,
                voltage,
                current,
                row_number() OVER (
                    PARTITION BY floor((extract(epoch FROM ts) - %(start_epoch)s) / %(bucket_seconds)s)
                    ORDER BY ts ASC
                ) AS rn_asc,
                row_number() OVER (
                    PARTITION BY floor((extract(epoch FROM ts) - %(start_epoch)s) / %(bucket_seconds)s)
                    ORDER BY ts DESC
                ) AS rn_desc
            FROM reading
            WHERE device_id = %(device_id)s AND ts >= %(start_utc)s AND ts <= %(end_utc)s
        )
        SELECT
            bucket_index,
            MIN(energy_kwh) FILTER (WHERE rn_asc = 1) AS first_energy,
            MAX(energy_kwh) FILTER (WHERE rn_desc = 1) AS last_energy,
            MAX(power) FILTER (WHERE rn_desc = 1) AS last_power,
            MAX(voltage) FILTER (WHERE rn_desc = 1) AS last_voltage,
            MAX(current) FILTER (WHERE rn_desc = 1) AS last_current
        FROM raw
        WHERE bucket_index >= 0 AND bucket_index < %(bucket_count)s
        GROUP BY bucket_index
        ORDER BY bucket_index;
        """
        params = {
            "device_id": str(device_id),
            "start_utc": start_utc,
            "end_utc": end_utc,
            "start_epoch": start_epoch,
            "bucket_seconds": bucket_seconds,
            "bucket_count": bucket_count,
        }
        rows = await sync_to_async(cls._run_bucket_query, thread_sensitive=True)(sql, params)

        bucket_map: Dict[int, Dict[str, float | int]] = {}
        for row in rows:
            idx = row.get("bucket_index")
            if idx is None:
                continue
            bucket_idx = int(idx)
            stats = cls._empty_bucket_stats()
            stats["count"] = 1
            stats["power"] = float(row.get("last_power") or 0.0)
            stats["voltage"] = float(row.get("last_voltage") or 0.0)
            stats["current"] = float(row.get("last_current") or 0.0)
            first_energy = row.get("first_energy")
            last_energy = row.get("last_energy")
            if first_energy is not None and last_energy is not None:
                delta = Decimal(last_energy) - Decimal(first_energy)
                if delta >= 0:
                    stats["energy"] = float(delta)
            bucket_map[bucket_idx] = stats

        buckets: List[tuple[datetime, Dict[str, float | int]]] = []
        for idx in range(bucket_count):
            bucket_ts = start_utc + config.bucket * idx
            stats = bucket_map.get(idx, cls._empty_bucket_stats())
            buckets.append((bucket_ts, stats))
        return buckets

    @staticmethod
    def _run_bucket_query(sql: str, params: Dict[str, object]) -> List[dict[str, object]]:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
