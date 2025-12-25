"""MQTT config helpers shared by ingestion and publish paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from apps.repositories.models import Device


@dataclass(frozen=True)
class MQTTConfig:
    broker: str
    port: int
    client_id: str
    username: str
    password: str
    sub_topic: Optional[str]
    pub_topic: Optional[str]


def resolve_mqtt_config(device: Device) -> MQTTConfig:
    config = device.ingress_config or {}
    broker = getattr(device, "broker", None) or config.get("broker")
    port = getattr(device, "port", None) or config.get("port")
    sub_topic = getattr(device, "sub_topic", None) or config.get("topic") or config.get("sub_topic")
    pub_topic = getattr(device, "pub_topic", None) or config.get("pub_topic")
    username = getattr(device, "username", "") or config.get("username") or ""
    password = getattr(device, "password", "") or config.get("password") or ""
    client_id = getattr(device, "client_id", "") or config.get("client_id") or ""

    if not broker or port is None:
        raise ValueError("MQTT config missing broker/port")
    if not client_id:
        raise ValueError("MQTT config missing client_id")

    return MQTTConfig(
        broker=str(broker),
        port=int(port),
        client_id=str(client_id),
        username=str(username),
        password=str(password),
        sub_topic=str(sub_topic) if sub_topic else None,
        pub_topic=str(pub_topic) if pub_topic else None,
    )


def build_broker_url(config: MQTTConfig) -> str:
    auth = f"{config.username}:{config.password}@" if config.username else ""
    return f"mqtt://{auth}{config.broker}:{config.port}"
