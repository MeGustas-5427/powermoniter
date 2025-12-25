"""Device admin routes implemented with Django Ninja."""

from __future__ import annotations

from http import HTTPStatus
from time import perf_counter
from typing import Optional

from django.http import HttpRequest
from ninja import Router
from ninja.params import Query

from apps.api.dependencies.security import AuthContext, JWTAuth
from apps.api.errors import ApiError
from apps.repositories.device_repository import DeviceRepository
from apps.repositories.models import DeviceStatus
from apps.schemas.devices import (
    DeviceCreate,
    DeviceListResponse,
    DevicePublishPayload,
    DevicePublishResponse,
    DeviceResponse,
    DeviceUpdate,
)
from apps.services.subscription_manager import subscription_manager
from apps.services.mqtt_publish_service import MQTTPublishService
from apps.telemetry.metrics import observe_device_api

router = Router(tags=["Device Admin"], auth=JWTAuth())
_repository = DeviceRepository()


def _require_auth(request: HttpRequest) -> AuthContext:
    auth = getattr(request, "auth", None)
    if auth is None:
        raise ApiError("UNAUTHORIZED", "Missing Authorization header", HTTPStatus.UNAUTHORIZED)
    return auth


@router.post(
    "/macs",
    response={HTTPStatus.CREATED: DeviceResponse},
    summary="Create device by MAC",
)
async def create_device(
    request: HttpRequest,
    payload: DeviceCreate,
) -> tuple[int, DeviceResponse]:
    """Create a device and register it with the subscription manager."""

    status_label = "success"
    started = perf_counter()
    try:
        _require_auth(request)
        mac_value = _normalize_mac(payload.mac)
        try:
            device = await DeviceRepository.create_device(
                mac=mac_value,
                status=payload.status,
                collect_enabled=payload.collect_enabled,
                ingress_type=payload.ingress_type,
                ingress_config=payload.ingress_config,
                description=payload.description,
            )
        except ValueError as exc:
            status_label = "DEVICE_CONFLICT"
            raise ApiError(
                "DEVICE_CONFLICT",
                "device with this MAC already exists",
                HTTPStatus.CONFLICT,
            ) from exc

        await subscription_manager.apply_device(device)
        return HTTPStatus.CREATED, DeviceResponse.from_model(device)
    except ApiError as exc:
        status_label = exc.error_code
        raise
    except Exception as exc:  # pragma: no cover
        status_label = "INTERNAL_ERROR"
        raise ApiError(
            "INTERNAL_ERROR",
            "unexpected server error",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from exc
    finally:
        observe_device_api(
            "device_admin_create",
            status_label,
            perf_counter() - started,
        )


@router.get(
    "/macs",
    response=DeviceListResponse,
    summary="List devices",
)
async def list_devices(
    request: HttpRequest,
    status_filter: Optional[DeviceStatus] = Query(None, alias="status"),
) -> DeviceListResponse:
    """List devices optionally filtered by status."""

    status_label = "success"
    started = perf_counter()
    items_count: Optional[int] = None
    try:
        _require_auth(request)
        devices = await _repository.list_devices(status=status_filter)
        items = [DeviceResponse.from_model(device) for device in devices]
        items_count = len(items)
        return DeviceListResponse(items=items, total=items_count)
    except ApiError as exc:
        status_label = exc.error_code
        raise
    except Exception as exc:  # pragma: no cover
        status_label = "INTERNAL_ERROR"
        raise ApiError(
            "INTERNAL_ERROR",
            "unexpected server error",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from exc
    finally:
        observe_device_api(
            "device_admin_list",
            status_label,
            perf_counter() - started,
            points=items_count if status_label == "success" else None,
        )


@router.patch(
    "/macs/{mac}",
    response=DeviceResponse,
    summary="Update a device by MAC",
)
async def update_device(
    request: HttpRequest,
    mac: str,
    payload: DeviceUpdate,
) -> DeviceResponse:
    """Update device attributes and refresh subscription."""

    status_label = "success"
    started = perf_counter()
    try:
        _require_auth(request)
        device = await _repository.update_device(
            _normalize_mac(mac),
            status=payload.status,
            collect_enabled=payload.collect_enabled,
            ingress_type=payload.ingress_type,
            ingress_config=payload.ingress_config,
            description=payload.description,
        )
        if device is None:
            status_label = "DEVICE_NOT_FOUND"
            raise ApiError(
                "DEVICE_NOT_FOUND",
                "specified device does not exist",
                HTTPStatus.NOT_FOUND,
            )

        await subscription_manager.apply_device(device)
        return DeviceResponse.from_model(device)
    except ApiError as exc:
        status_label = exc.error_code
        raise
    except Exception as exc:  # pragma: no cover
        status_label = "INTERNAL_ERROR"
        raise ApiError(
            "INTERNAL_ERROR",
            "unexpected server error",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from exc
    finally:
        observe_device_api(
            "device_admin_update",
            status_label,
            perf_counter() - started,
        )


@router.post(
    "/macs/{mac}/publish",
    response=DevicePublishResponse,
    summary="Publish device settings",
)
async def publish_device_settings(
    request: HttpRequest,
    mac: str,
    payload: DevicePublishPayload,
) -> DevicePublishResponse:
    """Publish device settings to MQTT."""

    status_label = "success"
    started = perf_counter()
    try:
        _require_auth(request)
        device = await _repository.get_by_mac(_normalize_mac(mac))
        if device is None:
            status_label = "DEVICE_NOT_FOUND"
            raise ApiError(
                "DEVICE_NOT_FOUND",
                "specified device does not exist",
                HTTPStatus.NOT_FOUND,
            )

        try:
            payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
            await MQTTPublishService.publish_settings(device, payload_data)
        except ValueError as exc:
            status_label = "INVALID_MQTT_CONFIG"
            raise ApiError(
                "INVALID_MQTT_CONFIG",
                str(exc),
                HTTPStatus.BAD_REQUEST,
            ) from exc
        except ConnectionError as exc:
            status_label = "MQTT_UNAVAILABLE"
            raise ApiError(
                "MQTT_UNAVAILABLE",
                "mqtt publish failed",
                HTTPStatus.SERVICE_UNAVAILABLE,
            ) from exc

        return DevicePublishResponse()
    except ApiError as exc:
        status_label = exc.error_code
        raise
    except Exception as exc:  # pragma: no cover
        status_label = "INTERNAL_ERROR"
        raise ApiError(
            "INTERNAL_ERROR",
            "unexpected server error",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from exc
    finally:
        observe_device_api(
            "device_admin_publish",
            status_label,
            perf_counter() - started,
        )

__all__ = ["router"]

def _normalize_mac(value: str) -> str:
    return value.strip().upper()
