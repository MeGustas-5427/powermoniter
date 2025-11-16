from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt
from django.conf import settings
from django.test import Client, TestCase, override_settings

from apps.repositories.models import DeviceStatus, IngressType, User
from apps.services.auth_service import JWT_ALGORITHM


class DeviceAdminRoutesTests(TestCase):
    """Django tests for /v1/device-admin/macs endpoints."""

    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create(username="alice", password="!", password_hash="!")

    def test_create_device_success(self) -> None:
        payload = self._build_device_payload(mac="cc0000000001")

        with patch(
            "apps.api.routes.devices.subscription_manager.apply_device",
            new=AsyncMock(),
        ) as mocked_apply:
            response = self.client.post(
                "/api/v1/device-admin/macs",
                data=json.dumps(payload),
                content_type="application/json",
                **self._auth_headers(),
            )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["mac"], payload["mac"].upper())
        mocked_apply.assert_awaited()

    def test_create_device_conflict(self) -> None:
        payload = self._build_device_payload(mac="cc0000000002")
        self._post_device(payload)

        response = self.client.post(
            "/api/v1/device-admin/macs",
            data=json.dumps(payload),
            content_type="application/json",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "DEVICE_CONFLICT")

    def test_list_devices_filters_by_status(self) -> None:
        self._post_device(self._build_device_payload(mac="cc0000000003", status=DeviceStatus.ENABLED.value))
        self._post_device(self._build_device_payload(mac="cc0000000004", status=DeviceStatus.DISABLED.value))

        response = self.client.get(
            "/api/v1/device-admin/macs",
            {"status": DeviceStatus.ENABLED.value},
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["status"], DeviceStatus.ENABLED.value)

    def test_update_device_success(self) -> None:
        mac = "cc0000000005"
        self._post_device(self._build_device_payload(mac=mac))

        with patch(
            "apps.api.routes.devices.subscription_manager.apply_device",
            new=AsyncMock(),
        ) as mocked_apply:
            response = self.client.patch(
                f"/api/v1/device-admin/macs/{mac}",
                data=json.dumps({"description": "updated", "collect_enabled": True}),
                content_type="application/json",
                **self._auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "updated")
        mocked_apply.assert_awaited()

    def test_update_device_not_found(self) -> None:
        response = self.client.patch(
            "/api/v1/device-admin/macs/ff0000000000",
            data=json.dumps({"description": "missing"}),
            content_type="application/json",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "DEVICE_NOT_FOUND")

    def test_requires_authorization(self) -> None:
        response = self.client.get("/api/v1/device-admin/macs")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get("detail"), "Unauthorized")

    # Helpers -----------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        secret = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
        payload = {
            "sub": str(self.user.id),
            "type": "access",
            "iat": now,
            "exp": now + timedelta(hours=1),
        }
        token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _build_device_payload(
        self,
        *,
        mac: str,
        status: int = DeviceStatus.ENABLED.value,
        ingress_type: int = IngressType.MQTT.value,
    ) -> dict[str, object]:
        return {
            "mac": mac,
            "status": status,
            "collect_enabled": False,
            "ingress_type": ingress_type,
            "ingress_config": {
                "name": f"device-{mac}",
                "location": "hangzhou",
                "broker": "mqtt.local",
                "port": 1883,
                "pub_topic": f"{mac}/pub",
                "sub_topic": f"{mac}/sub",
                "client_id": f"client-{mac}",
                "username": "device",
                "password": "secret",
            },
            "description": f"device {mac}",
        }

    def _post_device(self, payload: dict[str, object]) -> None:
        with patch(
            "apps.api.routes.devices.subscription_manager.apply_device",
            new=AsyncMock(),
        ):
            response = self.client.post(
                "/api/v1/device-admin/macs",
                data=json.dumps(payload),
                content_type="application/json",
                **self._auth_headers(),
            )
        self.assertEqual(response.status_code, 201)
