import json
import logging

import paho.mqtt.client as mqtt

from config import load_settings
from simulator.publisher import (
    QOS_AT_LEAST_ONCE,
    build_payload,
    create_client,
    on_connect,
    on_disconnect,
    publish_once,
)


class FakePublishResult:
    def __init__(self, rc):
        self.rc = rc


class FakeClient:
    """Stands in for paho's Client and records every publish call."""

    def __init__(self, rc=mqtt.MQTT_ERR_SUCCESS):
        self.rc = rc
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))
        return FakePublishResult(self.rc)


class FakeReasonCode:
    def __init__(self, is_failure):
        self.is_failure = is_failure

    def __str__(self):
        return "fake reason"


def test_build_payload_is_json_with_all_fields():
    data = json.loads(build_payload("MOTOR-002"))

    assert data["device_id"] == "MOTOR-002"
    assert set(data) == {
        "device_id",
        "timestamp",
        "temperature",
        "humidity",
        "vibration",
        "current",
    }


def test_publish_once_sends_one_message_per_device():
    settings = load_settings({"DEVICE_IDS": "MOTOR-001,MOTOR-002"})
    client = FakeClient()

    publish_once(client, settings)

    topics = [topic for topic, _, _ in client.published]
    device_ids = [json.loads(payload)["device_id"] for _, payload, _ in client.published]
    assert topics == ["factory/motor-001/telemetry", "factory/motor-002/telemetry"]
    assert device_ids == ["MOTOR-001", "MOTOR-002"]
    assert all(qos == QOS_AT_LEAST_ONCE for _, _, qos in client.published)


def test_publish_once_logs_warning_when_publish_fails(caplog):
    client = FakeClient(rc=mqtt.MQTT_ERR_NO_CONN)

    publish_once(client, load_settings({}))

    assert "failed" in caplog.text


def test_on_connect_logs_error_when_connection_fails(caplog):
    on_connect(None, None, None, FakeReasonCode(is_failure=True), None)

    assert "Connection to broker failed" in caplog.text


def test_on_connect_logs_info_when_connected(caplog):
    caplog.set_level(logging.INFO)

    on_connect(None, None, None, FakeReasonCode(is_failure=False), None)

    assert "Connected to broker" in caplog.text


def test_create_client_registers_callbacks():
    client = create_client(load_settings({}))

    assert client.on_connect is on_connect


def test_on_disconnect_logs_reason(caplog):
    caplog.set_level(logging.INFO)

    on_disconnect(None, None, None, "Normal disconnection", None)

    assert "Disconnected from broker: Normal disconnection" in caplog.text


def test_create_client_sets_credentials_when_username_is_given():
    settings = load_settings({"MQTT_USERNAME": "panel", "MQTT_PASSWORD": "secret"})

    client = create_client(settings)

    assert client.username == "panel"
