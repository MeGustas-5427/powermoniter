"""API 错误与统一响应封装"""

from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest, JsonResponse


@dataclass(slots=True)
class ApiError(Exception):
    """业务层抛出的统一错误类型"""

    error_code: str
    message: str
    status_code: int


def api_error_handler(_: HttpRequest, exc: ApiError) -> JsonResponse:
    """Ninja 异常处理回调，转换为 JSON 响应"""

    return JsonResponse(
        {
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
        },
        status=exc.status_code,
    )


__all__ = ["ApiError", "api_error_handler"]
