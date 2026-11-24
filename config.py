"""Application settings loaded from environment variables and the .env file."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Settings shared by the publisher, subscriber, API and dashboard."""

    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_topic_prefix: str
    device_ids: tuple[str, ...]
    publish_interval_seconds: float

    def telemetry_topic(self, device_id: str) -> str:
        """Return the MQTT topic used for a device's sensor readings."""
        return f"{self.mqtt_topic_prefix}/{device_id.lower()}/telemetry"


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from the given mapping, or from .env and os.environ if none is given."""
    if env is None:
        load_dotenv()
        env = os.environ

    port = int(env.get("MQTT_PORT", "1883"))
    interval = float(env.get("PUBLISH_INTERVAL_SECONDS", "2"))
    raw_devices = env.get("DEVICE_IDS", "MOTOR-001")
    device_ids = tuple(part.strip() for part in raw_devices.split(",") if part.strip())

    if not 1 <= port <= 65535:
        raise ValueError(f"MQTT_PORT must be between 1 and 65535, got {port}")
    if interval <= 0:
        raise ValueError(f"PUBLISH_INTERVAL_SECONDS must be positive, got {interval}")
    if not device_ids:
        raise ValueError("DEVICE_IDS must contain at least one device id")

    return Settings(
        mqtt_host=env.get("MQTT_HOST", "localhost"),
        mqtt_port=port,
        mqtt_username=env.get("MQTT_USERNAME") or None,
        mqtt_password=env.get("MQTT_PASSWORD") or None,
        mqtt_topic_prefix=env.get("MQTT_TOPIC_PREFIX", "factory"),
        device_ids=device_ids,
        publish_interval_seconds=interval,
    )
