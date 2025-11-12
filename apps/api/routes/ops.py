# """运维接口（健康检查、指标）。"""
#
# from __future__ import annotations
#
# from fastapi import APIRouter, Response
#
# from apps.settings import get_settings
# from apps.subscribers import registry
# from apps.telemetry.metrics import export_prometheus
#
#
# router = APIRouter(tags=["Operations"])
#
#
# @router.get("/health")
# async def health() -> dict[str, object]:
#     """返回服务健康状态。"""
#
#     snapshot = registry.snapshot()
#     settings = get_settings()
#     return {
#         "status": "ok",
#         "subscriber_count": len(snapshot),
#         "database": settings.database_url,
#         "last_checkpoint_at": None,
#     }
#
#
# @router.get("/metrics")
# async def metrics() -> Response:
#     """返回 Prometheus 指标文本。"""
#
#     data, content_type = export_prometheus()
#     return Response(content=data, media_type=content_type)
