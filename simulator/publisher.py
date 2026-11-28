"""Publish simulated sensor readings to the MQTT broker at a fixed interval."""

import json
import logging
import sys
import time

import paho.mqtt.client as mqtt

from config import Settings, load_settings
from simulator.sensor import generate_sensor_data

logger = logging.getLogger(__name__)

QOS_AT_LEAST_ONCE = 1
DEFAULT_CLIENT_ID = "sensor-publisher"


def build_payload(device_id: str) -> str:
    """Return one sensor reading for the device as a JSON string."""
    return json.dumps(generate_sensor_data(device_id))


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        logger.error("Connection to broker failed: %s", reason_code)
    else:
        logger.info("Connected to broker")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    logger.info("Disconnected from broker: %s", reason_code)


def create_client(settings: Settings, client_id: str = DEFAULT_CLIENT_ID) -> mqtt.Client:
    """Create an MQTT client configured from the settings.

    The broker drops an existing connection when another client connects with the
    same id, so each running instance needs its own client_id.
    """
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
    )
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    return client


def publish_once(client: mqtt.Client, settings: Settings) -> None:
    """Publish one reading for every configured device."""
    for device_id in settings.device_ids:
        topic = settings.telemetry_topic(device_id)
        result = client.publish(topic, build_payload(device_id), qos=QOS_AT_LEAST_ONCE)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning("Publish to %s failed with code %s", topic, result.rc)
        else:
            logger.info("Published reading to %s", topic)


def run(settings: Settings) -> None:
    """Connect to the broker and publish readings until interrupted with Ctrl+C."""
    client = create_client(settings)
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.loop_start()
    try:
        while True:
            publish_once(client, settings)
            time.sleep(settings.publish_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Stopping publisher")
    finally:
        client.disconnect()
        client.loop_stop()


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
