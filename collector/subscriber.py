"""Subscribe to device telemetry on the MQTT broker and store each reading in SQLite."""

import json
import logging
import math
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

import paho.mqtt.client as mqtt

from config import Settings, load_settings
from storage.database import MEASUREMENT_FIELDS, connect, insert_reading

logger = logging.getLogger(__name__)

QOS_AT_LEAST_ONCE = 1


@dataclass
class SubscriberContext:
    """State shared with the MQTT callbacks through the client's userdata."""

    settings: Settings
    conn: sqlite3.Connection


def parse_reading(topic: str, payload: bytes) -> dict[str, str | float]:
    """Validate a telemetry message and return it as a normalised reading.

    Raises ValueError when the payload is not a valid reading or its device id
    does not match the device segment of the topic.
    """
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"payload is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")

    device_id = data.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("device_id must be a non-empty string")
    device_id = device_id.strip()
    topic_parts = topic.split("/")
    if len(topic_parts) < 2 or topic_parts[-2] != device_id.lower():
        raise ValueError(f"device_id {device_id!r} does not match topic {topic!r}")

    raw_timestamp = data.get("timestamp")
    if not isinstance(raw_timestamp, str):
        raise ValueError("timestamp must be an ISO 8601 string")
    try:
        timestamp = datetime.fromisoformat(raw_timestamp)
    except ValueError as error:
        raise ValueError(f"timestamp is not ISO 8601: {raw_timestamp!r}") from error
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must include a time zone")

    reading: dict[str, str | float] = {
        "device_id": device_id,
        "timestamp": timestamp.astimezone(UTC).isoformat(),
    }
    for field in MEASUREMENT_FIELDS:
        value = data.get(field)
        # bool is a subclass of int, so reject it explicitly.
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{field} must be a number")
        if not math.isfinite(value):
            raise ValueError(f"{field} must be finite")
        reading[field] = float(value)
    return reading


def on_connect(client, userdata: SubscriberContext, flags, reason_code, properties):
    if reason_code.is_failure:
        logger.error("Connection to broker failed: %s", reason_code)
        return
    topic_filter = userdata.settings.telemetry_subscription
    # Subscribing here means the subscription is restored after every reconnect.
    client.subscribe(topic_filter, qos=QOS_AT_LEAST_ONCE)
    logger.info("Connected to broker, subscribed to %s", topic_filter)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    logger.info("Disconnected from broker: %s", reason_code)


def on_message(client, userdata: SubscriberContext, message):
    try:
        reading = parse_reading(message.topic, message.payload)
    except ValueError as error:
        logger.warning("Ignoring message on %s: %s", message.topic, error)
        return
    try:
        insert_reading(userdata.conn, reading)
    except sqlite3.Error:
        logger.exception("Could not store reading from %s", message.topic)
        return
    logger.info("Stored reading from %s", reading["device_id"])


def create_client(settings: Settings, conn: sqlite3.Connection) -> mqtt.Client:
    """Create an MQTT client that stores incoming readings through conn."""
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="sensor-subscriber",
        userdata=SubscriberContext(settings=settings, conn=conn),
    )
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    return client


def run(settings: Settings) -> None:
    """Connect to the broker and store readings until interrupted with Ctrl+C."""
    conn = connect(settings.database_path)
    logger.info("Writing readings to %s", settings.database_path)
    client = create_client(settings, conn)
    try:
        client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Stopping subscriber")
    finally:
        client.disconnect()
        conn.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        run(load_settings())
    except OSError as error:
        logger.error("Cannot reach MQTT broker: %s", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
