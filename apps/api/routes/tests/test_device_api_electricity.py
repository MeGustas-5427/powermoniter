from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import jwt
from django.conf import settings
from django.test import Client, TestCase, override_settings

from apps.repositories.models import Device, DeviceStatus, IngressType, Reading, User
from apps.services.auth_service import JWT_ALGORITHM
from apps.services.device_api_service import DeviceApiService


class DeviceApiElectricityTests(TestCase):
    """覆盖 /v1/devices/{id}/electricity 的 Django 测试。"""

    maxDiff = None

    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create(username="alice", password="!", password_hash="!")
        self.device = self._create_device("Main Device", "BB0000000001", user=self.user)
        self.fixed_now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    def test_get_device_electricity_returns_points_for_24h_window(self) -> None:
        older_ts = self.fixed_now - timedelta(hours=1)
        recent_ts = self.fixed_now - timedelta(minutes=5)
        recent_ts2 = self.fixed_now - timedelta(minutes=6)
        recent_ts3 = self.fixed_now - timedelta(minutes=7)
        recent_ts4 = self.fixed_now - timedelta(minutes=31)
        self._create_reading(self.device, older_ts, energy_kwh=Decimal("10.0"), power=Decimal("0.4"), voltage=Decimal("220.0"), current=Decimal("1.0"))
        self._create_reading(self.device, recent_ts4, energy_kwh=Decimal("10.2"), power=Decimal("1.4"), voltage=Decimal("221.1"), current=Decimal("1.4"))
        self._create_reading(self.device, recent_ts3, energy_kwh=Decimal("10.4"), power=Decimal("1.5"), voltage=Decimal("221.1"), current=Decimal("1.5"))
        self._create_reading(self.device, recent_ts2, energy_kwh=Decimal("10.7"), power=Decimal("1.6"), voltage=Decimal("221.2"), current=Decimal("1.6"))
        self._create_reading(self.device, recent_ts, energy_kwh=Decimal("11.2"), power=Decimal("1.7"), voltage=Decimal("221.3"), current=Decimal("1.7"))

        with self._freeze_now():
            response = self.client.get(
                f"/api/v1/devices/{self.device.id}/electricity",
                {"window": "24h"},
                **self._auth_headers(self.user),
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        print(body)
        a = {
            'success': True,
            'data': {
                'device_id': '019a8c01-2285-7037-89c0-1f2692558a32',
                'start_time': '2024-12-31T12:00:00Z',
                'end_time': '2025-01-01T12:00:00Z',
                'interval': 'pt5m',
                'points': [
                    {
                        'timestamp': '2025-01-01T11:00:00Z',
                        'power_kw': 0.4,
                        'energy_kwh': 0.0,
                        'voltage_v': 220.0,
                        'current_a': 1.0
                    }, {
                        'timestamp': '2025-01-01T11:25:00Z',
                        'power_kw': 1.4,
                        'energy_kwh': 0.2,
                        'voltage_v': 221.1,
                        'current_a': 1.4
                    }, {
                        'timestamp': '2025-01-01T11:50:00Z',
                        'power_kw': 1.6,
                        'energy_kwh': 0.5,
                        'voltage_v': 221.2,
                        'current_a': 1.6
                    }, {
                        'timestamp': '2025-01-01T11:55:00Z',
                        'power_kw': 1.7,
                        'energy_kwh': 0.5,
                        'voltage_v': 221.3,
                        'current_a': 1.7
                    }
                ]
            }
        }

        self.assertTrue(body["success"])
        data = body["data"]
        self.assertEqual(data["device_id"], str(self.device.id))
        self.assertEqual(data["interval"], "pt5m")
        self.assertEqual(data["start_time"], self._iso(self.fixed_now - timedelta(hours=24)))
        self.assertEqual(data["end_time"], self._iso(self.fixed_now))
        self.assertEqual(len(data["points"]), 4)
        first_point, _, _, second_point = data["points"]
        self.assertEqual(first_point["timestamp"], self._iso(older_ts.replace(second=0, microsecond=0)))
        self.assertEqual(second_point["timestamp"], self._iso(recent_ts.replace(second=0, microsecond=0)))
        self.assertAlmostEqual(first_point["power_kw"], 0.4, places=2)
        self.assertAlmostEqual(second_point["power_kw"], 1.7, places=2)

    def test_get_device_electricity_respects_all_windows(self) -> None:
        ts = self.fixed_now - timedelta(hours=2)
        self._create_reading(self.device, ts, energy_kwh=Decimal("5.0"), power=Decimal("0.8"), voltage=Decimal("219.0"), current=Decimal("0.8"))

        with self._freeze_now():
            resp_7d = self.client.get(
                f"/api/v1/devices/{self.device.id}/electricity",
                {"window": "7d"},
                **self._auth_headers(self.user),
            )

        with self._freeze_now():
            resp_30d = self.client.get(
                f"/api/v1/devices/{self.device.id}/electricity",
                {"window": "30d"},
                **self._auth_headers(self.user),
            )

        self.assertEqual(resp_7d.status_code, 200)
        self.assertEqual(resp_7d.json()["data"]["interval"], "pt30m")
        self.assertGreaterEqual(len(resp_7d.json()["data"]["points"]), 1)

        self.assertEqual(resp_30d.status_code, 200)
        self.assertEqual(resp_30d.json()["data"]["interval"], "pt120m")
        self.assertGreaterEqual(len(resp_30d.json()["data"]["points"]), 1)

    def test_get_device_electricity_returns_404_when_device_missing(self) -> None:
        stranger = User.objects.create(username="bob", password="!", password_hash="!")
        foreign_device = self._create_device("Foreign", "BB0000000002", user=stranger)

        response = self.client.get(
            f"/api/v1/devices/{foreign_device.id}/electricity",
            {"window": "24h"},
            **self._auth_headers(self.user),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "DEVICE_NOT_FOUND")

    def test_get_device_electricity_rejects_invalid_window(self) -> None:
        response = self.client.get(
            f"/api/v1/devices/{self.device.id}/electricity",
            {"window": "oops"},
            **self._auth_headers(self.user),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_TIME_RANGE")

    def test_get_device_electricity_requires_authorization_header(self) -> None:
        response = self.client.get(f"/api/v1/devices/{self.device.id}/electricity")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get("detail"), "Unauthorized")

    # Helpers -----------------------------------------------------------------

    def _auth_headers(self, user: User) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        secret = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
        payload = {"sub": str(user.id), "type": "access", "iat": now, "exp": now + timedelta(hours=1)}
        token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _freeze_now(self) -> patch:
        return patch("apps.api.routes.device_api.DeviceApiService._now", return_value=self.fixed_now)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _create_device(self, name: str, mac: str, *, user: User) -> Device:
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
            status=DeviceStatus.ENABLED.value,
            collect_enabled=True,
            description=f"{name} description",
            ingress_type=IngressType.MQTT.value,
            user=user,
        )

    def _create_reading(
        self,
        device: Device,
        ts: datetime,
        *,
        energy_kwh: Decimal,
        power: Decimal,
        voltage: Decimal,
        current: Decimal,
    ) -> Reading:
        return Reading.objects.create(
            device=device,
            mac=device.mac,
            ts=ts,
            energy_kwh=energy_kwh,
            power=power,
            voltage=voltage,
            current=current,
            key=None,
            payload={"source": "test"},
            payload_hash=f"{device.mac}-{ts.timestamp()}",
        )
