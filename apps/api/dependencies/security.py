"""JWT 认证依赖，提供 AuthContext"""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import List

import jwt
from django.conf import settings
from ninja.security import HttpBearer

from apps.api.errors import ApiError
from apps.services.auth_service import JWT_ALGORITHM


@dataclass(slots=True)
class AuthContext:
    """从 JWT 中解析出的用户上下文"""

    user_id: str
    roles: List[str] = field(default_factory=list)


class JWTAuth(HttpBearer):
    """Ninja HttpBearer 实现，解析并校验 JWT"""

    def authenticate(self, request, token: str) -> AuthContext:
        secret = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[JWT_ALGORITHM],
                options={"require": ["sub", "exp"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ApiError("UNAUTHORIZED", "Token expired", HTTPStatus.UNAUTHORIZED) from exc
        except jwt.InvalidTokenError as exc:
            raise ApiError("UNAUTHORIZED", "Invalid token", HTTPStatus.UNAUTHORIZED) from exc

        token_type = payload.get("type")
        if token_type not in (None, "access"):
            raise ApiError("FORBIDDEN", "Unsupported token type", HTTPStatus.FORBIDDEN)

        subject = payload.get("sub")
        if not subject:
            raise ApiError("UNAUTHORIZED", "Token missing subject", HTTPStatus.UNAUTHORIZED)

        roles = payload.get("roles") or []
        if not isinstance(roles, list):
            roles = [str(roles)]

        return AuthContext(user_id=str(subject), roles=[str(role) for role in roles])


__all__ = ["AuthContext", "JWTAuth"]
