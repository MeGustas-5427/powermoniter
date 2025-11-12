from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password

from apps.repositories.models import User


LOCK_THRESHOLD = 3
LOCK_WINDOW = timedelta(minutes=15)
ACCESS_TOKEN_EXPIRES = timedelta(days=30)
JWT_ALGORITHM = "HS256"

logger = logging.getLogger(__name__)


@dataclass
class LoginResult:
    token: str
    expires_at: datetime
    user: User


class AccountLockedError(Exception):
    """Raised when account is locked."""


class InvalidCredentialsError(Exception):
    """Raised when username/password mismatch."""


class AuthService:
    """Domain service for handling login."""

    @staticmethod
    async def login(username: str, password: str) -> LoginResult:
        user = await User.objects.filter(username=username).afirst()
        if not user:
            logger.warning(f"login.failed.user_not_found: {username}")
            raise InvalidCredentialsError

        now = datetime.now(timezone.utc)
        last_login = AuthService._ensure_aware(user.last_login_at)

        if user.pw_fail_count >= LOCK_THRESHOLD:
            if last_login and now - last_login < LOCK_WINDOW:
                remaining_seconds = (LOCK_WINDOW - (now - last_login)).total_seconds()
                logger.warning(f"login.failed.account_locked: {username}; remaining_seconds: {remaining_seconds}")
                raise AccountLockedError
            user.pw_fail_count = 0
            logger.info(f"login.cooldown_reset: {username}")

        user.last_login_at = now

        if not check_password(password, user.password_hash):
            user.pw_fail_count += 1
            await user.asave(update_fields=["pw_fail_count", "last_login_at"])
            if user.pw_fail_count >= LOCK_THRESHOLD:
                logger.warning(f"login.account_locked: {username}; fail_count: {user.pw_fail_count}")
                raise AccountLockedError
            logger.warning(f"login.failed.invalid_password: {username}; fail_count: {user.pw_fail_count}")
            raise InvalidCredentialsError

        user.pw_fail_count = 0
        await user.asave(update_fields=["pw_fail_count", "last_login_at"])

        expires_at = now + ACCESS_TOKEN_EXPIRES
        secret = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
        access_token = AuthService._create_token(str(user.id), ACCESS_TOKEN_EXPIRES, "access", secret, issued_at=now)
        logger.info(f"login.success: {username}")
        return LoginResult(
            token=access_token,
            expires_at=expires_at,
            user=user,
        )

    @staticmethod
    def _ensure_aware(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _create_token(
        subject: str,
        expires_delta: timedelta,
        token_type: str,
        secret: str,
        *,
        issued_at: Optional[datetime] = None,
    ) -> str:
        now = issued_at or datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "type": token_type,
            "iat": now,
            "exp": now + expires_delta,
        }
        token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
        return token
