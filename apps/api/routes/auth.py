"""Auth routes implemented with Django Ninja."""

from __future__ import annotations

from http import HTTPStatus
from time import perf_counter
from datetime import datetime, timezone

from django.http import HttpRequest
from ninja import Router

from apps.api.errors import ApiError
from apps.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LoginPayload,
    LoginUserInfo,
)
from apps.services.auth_service import (
    AuthService,
    AccountLockedError,
    InvalidCredentialsError,
    ACCESS_TOKEN_EXPIRES,
    LoginResult,
)
from apps.telemetry.metrics import observe_device_api

router = Router(tags=["Auth"])


def _format_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_response(result: LoginResult) -> LoginResponse:
    user = result.user
    last_login = user.last_login_at or (result.expires_at - ACCESS_TOKEN_EXPIRES)
    return LoginResponse(
        success=True,
        data=LoginPayload(
            token=result.token,
            expires_at=_format_dt(result.expires_at),
            user=LoginUserInfo(
                user_id=str(user.id),
                username=user.username,
                last_login_at=_format_dt(last_login),
            ),
        ),
    )


@router.post("/login", response=LoginResponse, summary="User login")
async def login(request: HttpRequest, payload: LoginRequest) -> LoginResponse:
    """Authenticate user credentials and return JWT token."""

    status_label = "success"
    started = perf_counter()
    try:
        result = await AuthService.login(payload.username, payload.password)
        return _build_response(result)
    except AccountLockedError as exc:
        status_label = "ACCOUNT_LOCKED"
        raise ApiError(
            "ACCOUNT_LOCKED",
            "account locked, retry after 15 minutes",
            HTTPStatus.UNAUTHORIZED,
        ) from exc
    except InvalidCredentialsError as exc:
        status_label = "UNAUTHORIZED"
        raise ApiError(
            "UNAUTHORIZED",
            "invalid username or password",
            HTTPStatus.UNAUTHORIZED,
        ) from exc
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
            "auth_login",
            status_label,
            perf_counter() - started,
        )


__all__ = ["router"]
