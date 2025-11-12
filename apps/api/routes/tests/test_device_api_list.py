from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import jwt
from django.conf import settings
from django.test import Client, TestCase, override_settings

from apps.repositories.models import Device, DeviceStatus, IngressType, Reading, User
from apps.services.auth_service import JWT_ALGORITHM


@override_settings(ROOT_URLCONF="apps.api.routes.tests.urls")
class DeviceApiListTests(TestCase):
    """覆盖 /v1/devices list_devices API 的 Django 测试。"""

    maxDiff = None

    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create(username="alice", password="!", password_hash="!")
        self.fixed_now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    def test_list_devices_filters_by_status_and_paginates(self) -> None:
        online = self._create_device("A-Online", "AA0000000001")
        offline = self._create_device("B-Offline", "AA0000000002")
        maintenance = self._create_device("C-Maintenance", "AA0000000003", collect_enabled=False)

        self._add_reading(online, self.fixed_now - timedelta(minutes=5))
        self._add_reading(offline, self.fixed_now - timedelta(hours=2))
        self._add_reading(maintenance, self.fixed_now - timedelta(minutes=1))

        with patch("apps.api.routes.device_api.DeviceApiService._now", return_value=self.fixed_now):
            response = self.client.get(
                "/v1/devices",
                {"status": "online", "page": 1, "page_size": 2},
                **self._auth_headers(self.user),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        data = payload["data"]
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 2)
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["device_id"], str(online.id))
        self.assertEqual(item["status"], "online")
        self.assertEqual(item["mac"], online.mac)
        self.assertEqual(item["last_seen_at"], "2025-01-01T11:55:00Z")

    def test_list_devices_returns_empty_when_user_has_no_devices(self) -> None:
        lone_user = User.objects.create(username="bob", password="!", password_hash="!")
        response = self.client.get("/v1/devices", **self._auth_headers(lone_user))

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["items"], [])

    def test_list_devices_requires_authorization_header(self) -> None:
        response = self.client.get("/v1/devices")

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body.get("detail"), "Unauthorized")

    def test_list_devices_rejects_page_size_above_limit(self) -> None:
        response = self.client.get(
            "/v1/devices",
            {"page_size": 200},
            **self._auth_headers(self.user),
        )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertIn("page_size", str(body))

    def test_list_devices_rejects_invalid_status_value(self) -> None:
        response = self.client.get(
            "/v1/devices",
            {"status": "oops"},
            **self._auth_headers(self.user),
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("status", str(response.json()))

    # Helpers -----------------------------------------------------------------

    def _auth_headers(self, user: User) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        secret = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
        payload = {
            "sub": str(user.id),
            "type": "access",
            "iat": now,
            "exp": now + timedelta(hours=1),
        }
        token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _create_device(
        self,
        name: str,
        mac: str,
        *,
        collect_enabled: bool = True,
        status: DeviceStatus = DeviceStatus.ENABLED,
    ) -> Device:
        return Device.objects.create(
            name=name,
            location="Hangzhou",
            mac=mac,
            broker="broker",
            port=1883,
            pub_topic=f"{mac}/pub",
            sub_topic=f"{mac}/sub",
            client_id=f"client-{mac}",
            username="device-user",
            password="secret",
            status=status.value,
            collect_enabled=collect_enabled,
            description=f"{name} description",
            ingress_type=IngressType.MQTT.value,
            user=self.user,
        )

    def _add_reading(self, device: Device, ts: datetime) -> Reading:
        return Reading.objects.create(
            device=device,
            mac=device.mac,
            ts=ts,
            energy_kwh=Decimal("1.23"),
            power=Decimal("0.45"),
            voltage=Decimal("220.0"),
            current=Decimal("1.0"),
            key=None,
            payload={"sample": True},
            payload_hash=f"{device.mac}-{ts.timestamp()}",
        )
