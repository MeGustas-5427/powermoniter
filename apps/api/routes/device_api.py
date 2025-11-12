"""Dashboard 设备 API（基于 Django Ninja）"""

from __future__ import annotations

from http import HTTPStatus
from time import perf_counter
from uuid import UUID

from django.http import HttpRequest
from ninja import Router
from ninja.params import Query

from apps.api.dependencies.security import AuthContext, JWTAuth
from apps.api.errors import ApiError
from apps.schemas.device_api import (
    ApiErrorSchema,
    DeviceListResponse,
    DeviceStatusFilter,
    DeviceWindow,
    ElectricityResponse,
)
from apps.services.device_api_service import (
    DeviceApiService,
    DeviceNotFoundError,
    InvalidTimeRangeError,
    PaginationParams,
)
from apps.telemetry.metrics import observe_device_api

router = Router(tags=["Device API"], auth=JWTAuth())

ERROR_RESPONSES = {
    400: ApiErrorSchema,
    401: ApiErrorSchema,
    403: ApiErrorSchema,
    404: ApiErrorSchema,
}
DEVICE_LIST_RESPONSES = {200: DeviceListResponse} | ERROR_RESPONSES
ELECTRICITY_RESPONSES = {200: ElectricityResponse} | ERROR_RESPONSES

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _require_auth(request: HttpRequest) -> AuthContext:
    auth = getattr(request, "auth", None)
    if auth is None:
        raise ApiError("UNAUTHORIZED", "Missing Authorization header", HTTPStatus.UNAUTHORIZED)
    return auth


@router.get(
    "",
    response=DEVICE_LIST_RESPONSES,
    summary="分页获取设备列表",
)
async def list_devices(
    request: HttpRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    status_filter: DeviceStatusFilter = Query(DeviceStatusFilter.ALL, alias="status"),
) -> DeviceListResponse:
    """返回当前用户的设备分页列表"""

    status_label = "success"
    item_count: int | None = None
    started = perf_counter()
    try:
        params = PaginationParams(page=page, size=page_size)
        auth = _require_auth(request)
        data = await DeviceApiService.list_devices(
            user_id=auth.user_id,
            status_filter=status_filter,
            params=params,
        )
        item_count = len(data.items)
        return DeviceListResponse(success=True, data=data)
    except ApiError as exc:
        status_label = exc.error_code
        raise
    except Exception as exc:  # pragma: no cover - 非预期异常
        status_label = "INTERNAL_ERROR"
        raise ApiError(
            "INTERNAL_ERROR",
            "unexpected server error",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from exc
    finally:
        observe_device_api(
            "list_devices",
            status_label,
            perf_counter() - started,
            points=item_count if status_label == "success" else None,
        )


@router.get(
    "/{device_id}/electricity",
    response=ELECTRICITY_RESPONSES,
    summary="获取固定窗口用电曲线",
)
async def get_device_electricity(
    request: HttpRequest,
    device_id: UUID,
    window: str = Query("24h", description="One of 24h, 7d, 30d"),
) -> ElectricityResponse:
    """返回 24h/7d/30d 的用电时间序列"""

    status_label = "success"
    point_count: int | None = None
    started = perf_counter()
    try:
        try:
            window_enum = DeviceWindow(window)
        except ValueError as exc:
            raise ApiError(
                "INVALID_TIME_RANGE",
                "window must be one of 24h, 7d, 30d",
                HTTPStatus.BAD_REQUEST,
            ) from exc

        auth = _require_auth(request)
        data = await DeviceApiService.get_device_electricity(
            device_id=device_id,
            user_id=auth.user_id,
            window=window_enum,
        )
        point_count = len(data.points)
        return ElectricityResponse(success=True, data=data)
    except DeviceNotFoundError as exc:
        status_label = "DEVICE_NOT_FOUND"
        raise ApiError(
            "DEVICE_NOT_FOUND",
            "device_id is invalid or no longer exists",
            HTTPStatus.NOT_FOUND,
        ) from exc
    except InvalidTimeRangeError as exc:
        status_label = "INVALID_TIME_RANGE"
        raise ApiError(
            "INVALID_TIME_RANGE",
            "window must be one of 24h, 7d, 30d",
            HTTPStatus.BAD_REQUEST,
        ) from exc
    except ApiError as exc:
        status_label = exc.error_code
        raise
    except Exception as exc:  # pragma: no cover - 非预期异常
        status_label = "INTERNAL_ERROR"
        raise ApiError(
            "INTERNAL_ERROR",
            "unexpected server error",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ) from exc
    finally:
        observe_device_api(
            "device_electricity",
            status_label,
            perf_counter() - started,
            points=point_count if status_label == "success" else None,
        )


__all__ = ["router"]
