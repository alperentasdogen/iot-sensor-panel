import importlib
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from storage.database import connect, insert_reading


def make_reading(device_id, hour, temperature=40.0):
    return {
        "device_id": device_id,
        "timestamp": f"2026-11-28T{hour:02d}:00:00+00:00",
        "temperature": temperature,
        "humidity": 50.0,
        "vibration": 3.5,
        "current": 8.2,
    }


@pytest.fixture
def database_path(tmp_path):
    path = str(tmp_path / "sensors.db")
    with closing(connect(path)) as conn:
        insert_reading(conn, make_reading("MOTOR-001", 9, temperature=20.0))
        insert_reading(conn, make_reading("MOTOR-001", 10, temperature=30.0))
        insert_reading(conn, make_reading("MOTOR-001", 11, temperature=40.0))
        insert_reading(conn, make_reading("MOTOR-002", 10, temperature=90.0))
    return path


@pytest.fixture
def client(database_path):
    return TestClient(create_app(database_path))


@pytest.fixture
def empty_client(tmp_path):
    return TestClient(create_app(str(tmp_path / "empty.db")))


def timestamps(response):
    return [reading["timestamp"] for reading in response.json()]


def test_health_reports_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_database_errors_return_503_without_internal_details(tmp_path):
    # A folder cannot be opened as a database file.
    client = TestClient(create_app(str(tmp_path)))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_devices_lists_count_and_time_range(client):
    response = client.get("/devices")

    assert response.status_code == 200
    assert response.json() == [
        {
            "device_id": "MOTOR-001",
            "reading_count": 3,
            "first_seen": "2026-11-28T09:00:00Z",
            "last_seen": "2026-11-28T11:00:00Z",
        },
        {
            "device_id": "MOTOR-002",
            "reading_count": 1,
            "first_seen": "2026-11-28T10:00:00Z",
            "last_seen": "2026-11-28T10:00:00Z",
        },
    ]


def test_devices_is_empty_list_without_readings(empty_client):
    assert empty_client.get("/devices").json() == []


def test_latest_readings_returns_one_reading_per_device(client):
    response = client.get("/readings/latest")

    assert response.status_code == 200
    body = response.json()
    assert [(r["device_id"], r["temperature"]) for r in body] == [
        ("MOTOR-001", 40.0),
        ("MOTOR-002", 90.0),
    ]
    assert set(body[0]) == {
        "id",
        "device_id",
        "timestamp",
        "temperature",
        "humidity",
        "vibration",
        "current",
        "received_at",
    }


def test_readings_are_newest_first_and_limited(client):
    response = client.get("/readings", params={"limit": 2})

    assert response.status_code == 200
    assert timestamps(response) == ["2026-11-28T11:00:00Z", "2026-11-28T10:00:00Z"]


def test_readings_filter_by_device(client):
    response = client.get("/readings", params={"device_id": "MOTOR-002"})

    assert [r["device_id"] for r in response.json()] == ["MOTOR-002"]


def test_readings_filter_by_time_range(client):
    response = client.get(
        "/readings",
        params={
            "device_id": "MOTOR-001",
            "since": "2026-11-28T10:00:00Z",
            "until": "2026-11-28T10:30:00Z",
        },
    )

    assert timestamps(response) == ["2026-11-28T10:00:00Z"]


def test_readings_accept_time_zone_offsets(client):
    # 13:00 in Istanbul (UTC+3) is 10:00 UTC.
    response = client.get(
        "/readings", params={"device_id": "MOTOR-001", "since": "2026-11-28T13:00:00+03:00"}
    )

    assert timestamps(response) == ["2026-11-28T11:00:00Z", "2026-11-28T10:00:00Z"]


@pytest.mark.parametrize(
    "params",
    [
        {"device_id": "MOTOR 001"},
        {"device_id": "x' OR '1'='1"},
        {"device_id": "A" * 65},
        {"limit": 0},
        {"limit": 1001},
        {"limit": "many"},
        {"since": "yesterday"},
    ],
)
def test_readings_reject_invalid_parameters(client, params):
    response = client.get("/readings", params=params)

    assert response.status_code == 422


def test_readings_reject_time_without_time_zone(client):
    response = client.get("/readings", params={"since": "2026-11-28T10:00:00"})

    assert response.status_code == 422
    assert "time zone" in response.json()["detail"]


def test_readings_reject_since_after_until(client):
    response = client.get(
        "/readings",
        params={"since": "2026-11-28T12:00:00Z", "until": "2026-11-28T10:00:00Z"},
    )

    assert response.status_code == 422
    assert "since" in response.json()["detail"]


def test_stats_returns_min_avg_max_per_device(client):
    response = client.get("/stats")

    assert response.status_code == 200
    first, second = response.json()
    assert first["device_id"] == "MOTOR-001"
    assert first["reading_count"] == 3
    assert first["temperature"] == {"min": 20.0, "avg": 30.0, "max": 40.0}
    assert first["humidity"] == {"min": 50.0, "avg": 50.0, "max": 50.0}
    assert second["device_id"] == "MOTOR-002"


def test_stats_filter_by_device_and_time(client):
    response = client.get(
        "/stats", params={"device_id": "MOTOR-001", "since": "2026-11-28T10:00:00Z"}
    )

    [only] = response.json()
    assert only["reading_count"] == 2
    assert only["temperature"] == {"min": 30.0, "avg": 35.0, "max": 40.0}


def test_stats_validates_parameters(client):
    assert client.get("/stats", params={"device_id": "bad id"}).status_code == 422
    assert client.get("/stats", params={"until": "2026-11-28T10:00:00"}).status_code == 422


def test_openapi_documents_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths) == {"/health", "/devices", "/readings/latest", "/readings", "/stats"}


def test_main_module_uses_database_path_from_settings(monkeypatch, tmp_path):
    path = str(tmp_path / "configured.db")
    monkeypatch.setenv("DATABASE_PATH", path)

    import api.main

    module = importlib.reload(api.main)

    assert module.app.state.database_path == path
