"""Publish MQTT settings via the shared connection pool."""

from __future__ import annotations

from typing import Dict

from apps.adapters.mqtt_adapter import MQTTConnectionKey, mqtt_pool
from apps.repositories.models import Device, IngressType
from apps.services.mqtt_config import build_broker_url, resolve_mqtt_config


class MQTTPublishService:
    @staticmethod
    async def publish_settings(device: Device, payload: Dict[str, object]) -> None:
        if device.ingress_type != IngressType.MQTT:
            raise ValueError("device ingress_type is not MQTT")

        config = resolve_mqtt_config(device)
        if not config.pub_topic:
            raise ValueError("MQTT config missing pub_topic")

        broker_url = build_broker_url(config)
        key = MQTTConnectionKey.from_broker_url(broker_url, config.client_id)
        await mqtt_pool.publish(key, config.pub_topic, payload)


__all__ = ["MQTTPublishService"]
