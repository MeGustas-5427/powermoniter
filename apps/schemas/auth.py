from __future__ import annotations

from pydantic import constr
from ninja import Schema

class LoginRequest(Schema):
    username: constr(min_length=1, max_length=64)  # type: ignore[valid-type]
    password: constr(min_length=6, max_length=128)  # type: ignore[valid-type]


class LoginUserInfo(Schema):
    user_id: str
    username: str
    last_login_at: str


class LoginPayload(Schema):
    token: str
    expires_at: str
    user: LoginUserInfo


class LoginResponse(Schema):
    success: bool = True
    data: LoginPayload
