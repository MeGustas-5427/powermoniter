"""Prometheus 指标注册中心"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# 订阅侧指标
INGRESS_COUNTER = Counter(
    "subscriber_ingress_total",
    "采集器拉取到的消息量",
    labelnames=("mac",),
)
COMMIT_COUNTER = Counter(
    "subscriber_commit_total",
    "落库成功的消息量",
    labelnames=("mac",),
)
RETRY_COUNTER = Counter(
    "subscriber_retries_total",
    "采集侧的重试次数",
    labelnames=("mac", "reason"),
)
RECONNECT_COUNTER = Counter(
    "subscriber_reconnects_total",
    "采集适配器重连次数",
    labelnames=("mac",),
)
DEAD_LETTER_COUNTER = Counter(
    "dead_letters_total",
    "死信数量",
    labelnames=("reason",),
)
DUPLICATE_COUNTER = Counter(
    "duplicates_total",
    "重复消息数量",
    labelnames=("mac",),
)

# 延迟相关
LAG_GAUGE = Gauge(
    "subscriber_lag_seconds",
    "采集端积压的秒数",
    labelnames=("mac",),
)
INGEST_LATENCY = Histogram(
    "ingestion_latency_seconds",
    "采集至入库的延迟",
    buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5),
)

# 运行态指标
ACTIVE_SUBSCRIBERS = Gauge(
    "subscriber_active_total",
    "活跃采集任务数量",
)
DEVICE_API_REQUESTS = Counter(
    "device_api_requests_total",
    "Device API 请求次数，按 endpoint/status 区分",
    labelnames=("endpoint", "status"),
)
DEVICE_API_LATENCY = Histogram(
    "device_api_latency_seconds",
    "Device API 请求耗时",
    labelnames=("endpoint",),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
DEVICE_API_POINTS = Histogram(
    "device_api_points",
    "Device API 返回的点位/记录数",
    labelnames=("endpoint",),
    buckets=(1, 10, 50, 100, 500, 1000, 2000, 5000),
)


def set_active_subscribers(count: int) -> None:
    """设置活跃采集数量"""

    ACTIVE_SUBSCRIBERS.set(count)


def mark_reconnect(mac: str) -> None:
    """记录适配器重连"""

    RECONNECT_COUNTER.labels(mac=mac).inc()


def mark_retry(mac: str, reason: str) -> None:
    """记录采集重试"""

    RETRY_COUNTER.labels(mac=mac, reason=reason).inc()


def set_lag(mac: str, lag_seconds: float) -> None:
    """设置采集延迟"""

    LAG_GAUGE.labels(mac=mac).set(lag_seconds)


def observe_device_api(endpoint: str, status: str, elapsed: float, *, points: int | None = None) -> None:
    """Device API 相关指标"""

    DEVICE_API_REQUESTS.labels(endpoint=endpoint, status=status).inc()
    DEVICE_API_LATENCY.labels(endpoint=endpoint).observe(elapsed)
    if points is not None:
        DEVICE_API_POINTS.labels(endpoint=endpoint).observe(points)


def export_prometheus() -> tuple[bytes, str]:
    """导出 Prometheus 文本及 Content-Type"""

    data = generate_latest()
    return data, CONTENT_TYPE_LATEST
