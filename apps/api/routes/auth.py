# from __future__ import annotations
#
# from datetime import datetime, timezone
#
# from fastapi import APIRouter, status
# from django.http import JsonResponse
#
# from apps.schemas.auth import (
#     LoginRequest,
#     LoginResponse,
#     LoginUserInfo,
#     LoginPayload,
# )
# from apps.services.auth_service import (
#     AuthService,
#     AccountLockedError,
#     InvalidCredentialsError,
#     ACCESS_TOKEN_EXPIRES,
# )
#
# router = APIRouter(prefix="/auth", tags=["Auth"])
#
#
# def _format_dt(value: datetime) -> str:
#     return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
#
#
# def _error_response(code: str, message: str, status_code: int) -> JsonResponse:
#     return JsonResponse(
#         status_code=status_code,
#         content={"success": False, "error_code": code, "message": message},
#     )
#
#
# @router.post("/login", response_model=LoginResponse)
# async def login(payload: LoginRequest) -> LoginResponse | JsonResponse:
#     try:
#         result = await AuthService.login(payload.username, payload.password)
#     except AccountLockedError:
#         return _error_response("ACCOUNT_LOCKED", "账户暂时锁定，请 15 分钟后重试", status.HTTP_401_UNAUTHORIZED)
#     except InvalidCredentialsError:
#         return _error_response("UNAUTHORIZED", "用户名或密码错误", status.HTTP_401_UNAUTHORIZED)
#
#     user = result.user
#     last_login = user.last_login_at or (result.expires_at - ACCESS_TOKEN_EXPIRES)
#     response = LoginResponse(
#         success=True,
#         data=LoginPayload(
#             token=result.token,
#             expires_at=_format_dt(result.expires_at),
#             user=LoginUserInfo(
#                 user_id=str(user.id),
#                 username=user.username,
#                 last_login_at=_format_dt(last_login),
#             ),
#         ),
#     )
#     return response
