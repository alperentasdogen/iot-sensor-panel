import json
import logging
import sqlite3

import pytest

from collector.subscriber import (
    QOS_AT_LEAST_ONCE,
    SubscriberContext,
    create_client,
    on_connect,
    on_disconnect,
    on_message,
    parse_reading,
)
from config import load_settings
from simulator.publisher import build_payload
from storage.database import connect, fetch_latest

TOPIC = "factory/motor-001/telemetry"


def make_payload(**overrides):
    data = {
        "device_id": "MOTOR-001",
        "timestamp": "2026-11-27T13:00:00+03:00",
        "temperature": 40,
        "humidity": 50.5,
        "vibration": 3.5,
        "current": 8.2,
    }
    data.update(overrides)
    return json.dumps(data).encode()


class FakeMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


class FakeClient:
    def __init__(self):
        self.subscriptions = []

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))


class FakeReasonCode:
    def __init__(self, is_failure):
        self.is_failure = is_failure

    def __str__(self):
        return "fake reason"


@pytest.fixture
def context():
    conn = connect(":memory:")
    yield SubscriberContext(settings=load_settings({}), conn=conn)
    conn.close()


def test_parse_reading_normalises_values():
    reading = parse_reading(TOPIC, make_payload())

    assert reading == {
        "device_id": "MOTOR-001",
        "timestamp": "2026-11-27T10:00:00+00:00",
        "temperature": 40.0,
        "humidity": 50.5,
        "vibration": 3.5,
        "current": 8.2,
    }


def test_parse_reading_accepts_simulator_payload():
    payload = build_payload("MOTOR-002").encode()

    reading = parse_reading("factory/motor-002/telemetry", payload)

    assert reading["device_id"] == "MOTOR-002"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"not json", "JSON"),
        (b"\xff\xfe", "JSON"),
        (b"[1, 2]", "JSON object"),
        (make_payload(device_id=""), "device_id"),
        (make_payload(device_id=7), "device_id"),
        (make_payload(device_id="MOTOR-002"), "does not match topic"),
        (make_payload(timestamp=None), "timestamp"),
        (make_payload(timestamp="yesterday"), "ISO 8601"),
        (make_payload(timestamp="2026-11-27T10:00:00"), "time zone"),
        (make_payload(temperature="hot"), "temperature"),
        (make_payload(humidity=True), "humidity"),
        (make_payload(vibration=None), "vibration"),
        (
            b'{"device_id": "MOTOR-001", "timestamp": "2026-11-27T10:00:00+00:00", '
            b'"temperature": NaN, "humidity": 1, "vibration": 1, "current": 1}',
            "finite",
        ),
    ],
)
def test_parse_reading_rejects_invalid_messages(payload, message):
    with pytest.raises(ValueError, match=message):
        parse_reading(TOPIC, payload)


def test_on_message_stores_valid_reading(context):
    on_message(None, context, FakeMessage(TOPIC, make_payload()))

    rows = fetch_latest(context.conn)
    assert len(rows) == 1
    assert rows[0]["device_id"] == "MOTOR-001"


def test_on_message_ignores_invalid_reading(context, caplog):
    on_message(None, context, FakeMessage(TOPIC, b"not json"))

    assert fetch_latest(context.conn) == []
    assert "Ignoring message" in caplog.text


def test_on_message_logs_database_errors(caplog):
    conn = sqlite3.connect(":memory:")  # no schema, so the insert fails
    context = SubscriberContext(settings=load_settings({}), conn=conn)

    on_message(None, context, FakeMessage(TOPIC, make_payload()))

    assert "Could not store reading" in caplog.text
    conn.close()


def test_on_connect_subscribes_to_all_devices(context, caplog):
    caplog.set_level(logging.INFO)
    client = FakeClient()

    on_connect(client, context, None, FakeReasonCode(is_failure=False), None)

    assert client.subscriptions == [("factory/+/telemetry", QOS_AT_LEAST_ONCE)]


def test_on_connect_does_not_subscribe_when_connection_fails(context, caplog):
    client = FakeClient()

    on_connect(client, context, None, FakeReasonCode(is_failure=True), None)

    assert client.subscriptions == []
    assert "Connection to broker failed" in caplog.text


def test_on_disconnect_logs_reason(caplog):
    caplog.set_level(logging.INFO)

    on_disconnect(None, None, None, "Normal disconnection", None)

    assert "Disconnected from broker: Normal disconnection" in caplog.text


def test_create_client_registers_callbacks_and_credentials(context):
    settings = load_settings({"MQTT_USERNAME": "panel", "MQTT_PASSWORD": "secret"})

    client = create_client(settings, context.conn)

    assert client.on_message is on_message
    assert client.on_connect is on_connect
    assert client.username == "panel"
    assert client.user_data_get().conn is context.conn
