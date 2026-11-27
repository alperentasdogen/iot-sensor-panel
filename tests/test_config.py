from dataclasses import FrozenInstanceError

import pytest

from config import load_settings


def test_defaults_are_used_when_env_is_empty():
    settings = load_settings({})

    assert settings.mqtt_host == "localhost"
    assert settings.mqtt_port == 1883
    assert settings.mqtt_username is None
    assert settings.mqtt_password is None
    assert settings.mqtt_topic_prefix == "factory"
    assert settings.device_ids == ("MOTOR-001",)
    assert settings.publish_interval_seconds == 2.0


def test_values_are_read_from_env():
    settings = load_settings(
        {
            "MQTT_HOST": "broker.local",
            "MQTT_PORT": "8883",
            "MQTT_USERNAME": "panel",
            "MQTT_PASSWORD": "secret",
            "MQTT_TOPIC_PREFIX": "plant1",
            "DEVICE_IDS": "MOTOR-001,MOTOR-002",
            "PUBLISH_INTERVAL_SECONDS": "0.5",
        }
    )

    assert settings.mqtt_host == "broker.local"
    assert settings.mqtt_port == 8883
    assert settings.mqtt_username == "panel"
    assert settings.mqtt_password == "secret"
    assert settings.mqtt_topic_prefix == "plant1"
    assert settings.device_ids == ("MOTOR-001", "MOTOR-002")
    assert settings.publish_interval_seconds == 0.5


def test_empty_credentials_become_none():
    settings = load_settings({"MQTT_USERNAME": "", "MQTT_PASSWORD": ""})

    assert settings.mqtt_username is None
    assert settings.mqtt_password is None


def test_device_ids_are_trimmed_and_empty_entries_ignored():
    settings = load_settings({"DEVICE_IDS": " MOTOR-001 , ,MOTOR-002,"})

    assert settings.device_ids == ("MOTOR-001", "MOTOR-002")


@pytest.mark.parametrize("port", ["0", "-1", "65536"])
def test_out_of_range_port_raises(port):
    with pytest.raises(ValueError, match="MQTT_PORT"):
        load_settings({"MQTT_PORT": port})


def test_non_numeric_port_raises():
    with pytest.raises(ValueError):
        load_settings({"MQTT_PORT": "abc"})


@pytest.mark.parametrize("interval", ["0", "-2"])
def test_non_positive_interval_raises(interval):
    with pytest.raises(ValueError, match="PUBLISH_INTERVAL_SECONDS"):
        load_settings({"PUBLISH_INTERVAL_SECONDS": interval})


def test_empty_device_list_raises():
    with pytest.raises(ValueError, match="DEVICE_IDS"):
        load_settings({"DEVICE_IDS": " , "})


def test_telemetry_topic_uses_prefix_and_lowercase_device_id():
    settings = load_settings({"MQTT_TOPIC_PREFIX": "plant1"})

    assert settings.telemetry_topic("MOTOR-002") == "plant1/motor-002/telemetry"


def test_settings_cannot_be_modified():
    settings = load_settings({})

    with pytest.raises(FrozenInstanceError):
        settings.mqtt_port = 9999


def test_reads_os_environ_when_no_mapping_is_given(monkeypatch):
    monkeypatch.setenv("MQTT_HOST", "env-host")
    monkeypatch.setenv("MQTT_PORT", "1884")
    monkeypatch.setenv("MQTT_USERNAME", "")
    monkeypatch.setenv("MQTT_PASSWORD", "")
    monkeypatch.setenv("MQTT_TOPIC_PREFIX", "env-prefix")
    monkeypatch.setenv("DEVICE_IDS", "MOTOR-009")
    monkeypatch.setenv("PUBLISH_INTERVAL_SECONDS", "1")

    settings = load_settings()

    assert settings.mqtt_host == "env-host"
    assert settings.mqtt_port == 1884
    assert settings.mqtt_username is None
    assert settings.mqtt_topic_prefix == "env-prefix"
    assert settings.device_ids == ("MOTOR-009",)
    assert settings.publish_interval_seconds == 1.0


def test_database_path_defaults_and_can_be_overridden():
    assert load_settings({}).database_path == "data/sensors.db"
    assert load_settings({"DATABASE_PATH": "tmp/x.db"}).database_path == "tmp/x.db"


def test_empty_database_path_raises():
    with pytest.raises(ValueError, match="DATABASE_PATH"):
        load_settings({"DATABASE_PATH": "  "})


def test_telemetry_subscription_matches_every_device():
    settings = load_settings({"MQTT_TOPIC_PREFIX": "plant1"})

    assert settings.telemetry_subscription == "plant1/+/telemetry"
