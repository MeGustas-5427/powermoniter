from __future__ import annotations

import asyncio
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TestCase

from apps.adapters.mqtt_adapter import MQTTConnectionKey, SharedMQTTConnection, TopicSubscription


class SharedMQTTConnectionRoutingTests(TestCase):
    def _make_connection(self) -> SharedMQTTConnection:
        key = MQTTConnectionKey(host="broker", port=1883, username="", password="", client_id="client-1")
        return SharedMQTTConnection(key=key)

    def test_routes_matching_message(self) -> None:
        connection = self._make_connection()
        queue: asyncio.Queue = asyncio.Queue()
        connection._topics["device/sub"] = TopicSubscription(mac="AA0000000001", queue=queue)

        with patch("apps.adapters.mqtt_adapter.subscribers_registry.record_ingress") as mocked_ingress:
            async_to_sync(connection._handle_message)("device/sub", {"mac": "AA0000000001"})

        self.assertEqual(queue.qsize(), 1)
        mocked_ingress.assert_called_once_with("AA0000000001")

    def test_drops_unknown_topic(self) -> None:
        connection = self._make_connection()

        with patch("apps.adapters.mqtt_adapter.subscribers_registry.record_dead_letter") as mocked_dead_letter:
            async_to_sync(connection._handle_message)("unknown/sub", {"mac": "AA0000000001"})

        mocked_dead_letter.assert_called_once_with("unknown_topic")

    def test_drops_mac_mismatch(self) -> None:
        connection = self._make_connection()
        queue: asyncio.Queue = asyncio.Queue()
        connection._topics["device/sub"] = TopicSubscription(mac="AA0000000001", queue=queue)

        with patch("apps.adapters.mqtt_adapter.subscribers_registry.record_dead_letter") as mocked_dead_letter:
            async_to_sync(connection._handle_message)("device/sub", {"mac": "AA0000000002"})

        self.assertEqual(queue.qsize(), 0)
        mocked_dead_letter.assert_called_once_with("mac_mismatch")
