from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from django.test import Client, TestCase, override_settings

from apps.repositories.models import User
from apps.services.auth_service import (
    LoginResult,
    AccountLockedError,
    InvalidCredentialsError,
)


@override_settings(ROOT_URLCONF="apps.api.routes.tests.urls")
class AuthRoutesTests(TestCase):
    """Tests for /v1/auth/login endpoint."""

    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create(username="alice", password_hash="hash", password="!")
        self.expires_at = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    def test_login_success(self) -> None:
        mock_result = LoginResult(token="token-123", expires_at=self.expires_at, user=self.user)
        with patch("apps.api.routes.auth.AuthService.login", new=AsyncMock(return_value=mock_result)):
            response = self.client.post(
                "/v1/auth/login",
                data=json.dumps({"username": "alice", "password": "secret"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["token"], "token-123")
        self.assertEqual(data["data"]["user"]["username"], "alice")
        self.assertIn("T", data["data"]["expires_at"])

    def test_login_account_locked(self) -> None:
        with patch(
            "apps.api.routes.auth.AuthService.login",
            new=AsyncMock(side_effect=AccountLockedError),
        ):
            response = self.client.post(
                "/v1/auth/login",
                data=json.dumps({"username": "alice", "password": "secret"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error_code"], "ACCOUNT_LOCKED")

    def test_login_invalid_credentials(self) -> None:
        with patch(
            "apps.api.routes.auth.AuthService.login",
            new=AsyncMock(side_effect=InvalidCredentialsError),
        ):
            response = self.client.post(
                "/v1/auth/login",
                data=json.dumps({"username": "alice", "password": "invalid123"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error_code"], "UNAUTHORIZED")
