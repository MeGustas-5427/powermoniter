# """设备管理路由。"""
#
# from __future__ import annotations
#
# from typing import Optional
#
# from fastapi import APIRouter, Depends, HTTPException, Query, status
#
# from apps.repositories.device_repository import DeviceRepository
# from apps.repositories.models import DeviceStatus
# from apps.schemas.devices import (
#     DeviceCreate,
#     DeviceListResponse,
#     DeviceResponse,
#     DeviceUpdate,
# )
# from apps.services.subscription_manager import subscription_manager
#
#
# router = APIRouter(prefix="/macs", tags=["Devices"])
#
#
# def get_device_repository() -> DeviceRepository:
#     return DeviceRepository()
#
#
# @router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
# async def create_device(
#     payload: DeviceCreate,
#     repo: DeviceRepository = Depends(get_device_repository),
# ) -> DeviceResponse:
#     device = await repo.get_by_mac(payload.mac)
#     if device:
#         raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MAC 已存在")
#
#     device = await repo.create_device(
#         mac=payload.mac,
#         status=payload.status,
#         collect_enabled=payload.collect_enabled,
#         ingress_type=payload.ingress_type,
#         ingress_config=payload.ingress_config,
#         description=payload.description,
#     )
#
#     await subscription_manager.apply_device(device)
#     return DeviceResponse.from_model(device)
#
#
# @router.get("", response_model=DeviceListResponse)
# async def list_devices(
#     status_filter: Optional[DeviceStatus] = Query(None, alias="status"),
#     repo: DeviceRepository = Depends(get_device_repository),
# ) -> DeviceListResponse:
#     devices = await repo.list_devices(status=status_filter)
#     items = [DeviceResponse.from_model(device) for device in devices]
#     return DeviceListResponse(items=items, total=len(items))
#
#
# @router.patch("/{mac}", response_model=DeviceResponse)
# async def update_device(
#     mac: str,
#     payload: DeviceUpdate,
#     repo: DeviceRepository = Depends(get_device_repository),
# ) -> DeviceResponse:
#     device = await repo.update_device(
#         mac,
#         status=payload.status,
#         collect_enabled=payload.collect_enabled,
#         ingress_type=payload.ingress_type,
#         ingress_config=payload.ingress_config,
#         description=payload.description,
#     )
#     if device is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
#
#     await subscription_manager.apply_device(device)
#     return DeviceResponse.from_model(device)
