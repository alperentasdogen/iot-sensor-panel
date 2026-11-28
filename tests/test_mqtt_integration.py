"""End-to-end tests: publisher -> MQTT broker -> subscriber -> SQLite.

These tests need a running broker (MQTT_HOST/MQTT_PORT, default localhost:1883)
and are skipped when none is reachable, for example in CI.
"""

import json
import os
import socket
import threading
import time
import uuid
from contextlib import closing

import pytest

from collector import subscriber
from config import load_settings
from simulator import publisher
from storage.database import connect, fetch_latest

BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
TIMEOUT_SECONDS = 5.0


def broker_is_reachable() -> bool:
    try:
        with socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not broker_is_reachable(),
        reason=f"no MQTT broker at {BROKER_HOST}:{BROKER_PORT}",
    ),
]


def wait_until(condition, timeout=TIMEOUT_SECONDS) -> bool:
    """Poll condition until it is true or the timeout passes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def stored_rows(database_path: str) -> list[dict]:
    with closing(connect(database_path)) as conn:
        return fetch_latest(conn)


@pytest.fixture
def settings(tmp_path):
    # A unique topic prefix keeps the test apart from a publisher that may be
    # running against the same broker.
    return load_settings(
        {
            "MQTT_HOST": BROKER_HOST,
            "MQTT_PORT": str(BROKER_PORT),
            "MQTT_USERNAME": os.environ.get("MQTT_USERNAME", ""),
            "MQTT_PASSWORD": os.environ.get("MQTT_PASSWORD", ""),
            "MQTT_TOPIC_PREFIX": f"test-{uuid.uuid4().hex[:8]}",
            "DEVICE_IDS": "MOTOR-001,MOTOR-002",
            "DATABASE_PATH": str(tmp_path / "sensors.db"),
        }
    )


@pytest.fixture
def running_subscriber(settings):
    """Run the subscriber in a background thread until the test ends."""
    subscribed = threading.Event()
    clients = []

    def run():
        # SQLite connections may only be used by the thread that created them,
        # so the connection is opened here, like subscriber.run() does.
        with closing(connect(settings.database_path)) as conn:
            client = subscriber.create_client(
                settings, conn, client_id=f"{settings.mqtt_topic_prefix}-subscriber"
            )
            client.on_subscribe = lambda *args: subscribed.set()
            clients.append(client)
            client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
            client.loop_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        assert subscribed.wait(TIMEOUT_SECONDS), "subscriber did not subscribe in time"
        yield
    finally:
        for client in clients:
            client.disconnect()
        thread.join(TIMEOUT_SECONDS)


@pytest.fixture
def publisher_client(settings):
    client = publisher.create_client(settings, client_id=f"{settings.mqtt_topic_prefix}-publisher")
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.loop_start()
    try:
        assert wait_until(client.is_connected), "publisher did not connect in time"
        yield client
    finally:
        client.disconnect()
        client.loop_stop()


@pytest.mark.usefixtures("running_subscriber")
def test_published_readings_are_stored_for_every_device(settings, publisher_client):
    publisher.publish_once(publisher_client, settings)

    assert wait_until(lambda: len(stored_rows(settings.database_path)) == 2)
    rows = stored_rows(settings.database_path)
    assert {row["device_id"] for row in rows} == {"MOTOR-001", "MOTOR-002"}


@pytest.mark.usefixtures("running_subscriber")
def test_invalid_message_is_skipped_and_valid_one_stored_unchanged(settings, publisher_client):
    topic = settings.telemetry_topic("MOTOR-001")
    reading = {
        "device_id": "MOTOR-001",
        "timestamp": "2026-11-28T09:00:00+00:00",
        "temperature": 91.5,
        "humidity": 40.0,
        "vibration": 2.25,
        "current": 12.0,
    }

    # MQTT keeps the order of QoS 1 messages from one client on one topic, so
    # once the valid reading is stored the invalid one has been handled too.
    publisher_client.publish(topic, b"not json", qos=1)
    publisher_client.publish(topic, json.dumps(reading), qos=1)

    assert wait_until(lambda: len(stored_rows(settings.database_path)) >= 1)
    rows = stored_rows(settings.database_path)
    assert len(rows) == 1
    stored = {key: rows[0][key] for key in reading}
    assert stored == reading
