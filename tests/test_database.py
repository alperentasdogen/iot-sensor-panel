import sqlite3
import threading
from datetime import UTC, datetime, timedelta, timezone

import pytest

from storage.database import (
    connect,
    fetch_latest,
    insert_reading,
    latest_per_device,
    list_devices,
    reading_stats,
)


def make_reading(device_id="MOTOR-001", timestamp="2026-11-27T10:00:00+00:00", temperature=40.0):
    return {
        "device_id": device_id,
        "timestamp": timestamp,
        "temperature": temperature,
        "humidity": 50.0,
        "vibration": 3.5,
        "current": 8.2,
    }


@pytest.fixture
def conn():
    connection = connect(":memory:")
    yield connection
    connection.close()


def test_connect_creates_folder_and_file(tmp_path):
    path = tmp_path / "nested" / "sensors.db"

    connection = connect(str(path))
    connection.close()

    assert path.exists()


def test_inserted_reading_can_be_read_back(conn):
    row_id = insert_reading(conn, make_reading())

    rows = fetch_latest(conn)

    assert len(rows) == 1
    assert rows[0]["id"] == row_id
    assert rows[0]["device_id"] == "MOTOR-001"
    assert rows[0]["temperature"] == 40.0
    assert rows[0]["received_at"]


def test_fetch_latest_returns_newest_first_and_respects_limit(conn):
    for hour in ("09", "11", "10"):
        insert_reading(conn, make_reading(timestamp=f"2026-11-27T{hour}:00:00+00:00"))

    rows = fetch_latest(conn, limit=2)

    assert [row["timestamp"][11:13] for row in rows] == ["11", "10"]


def test_fetch_latest_filters_by_device(conn):
    insert_reading(conn, make_reading(device_id="MOTOR-001"))
    insert_reading(conn, make_reading(device_id="MOTOR-002"))

    rows = fetch_latest(conn, device_id="MOTOR-002")

    assert [row["device_id"] for row in rows] == ["MOTOR-002"]


def test_fetch_latest_rejects_non_positive_limit(conn):
    with pytest.raises(ValueError, match="limit"):
        fetch_latest(conn, limit=0)


def test_data_survives_reconnect(tmp_path):
    path = str(tmp_path / "sensors.db")
    first = connect(path)
    insert_reading(first, make_reading())
    first.close()

    second = connect(path)
    rows = fetch_latest(second)
    second.close()

    assert len(rows) == 1


def at(hour):
    return f"2026-11-27T{hour:02d}:00:00+00:00"


def test_fetch_latest_filters_by_time_range_inclusive(conn):
    for hour in (9, 10, 11, 12):
        insert_reading(conn, make_reading(timestamp=at(hour)))

    rows = fetch_latest(
        conn,
        since=datetime(2026, 11, 27, 10, tzinfo=UTC),
        until=datetime(2026, 11, 27, 11, tzinfo=UTC),
    )

    assert [row["timestamp"] for row in rows] == [at(11), at(10)]


def test_time_filters_are_converted_to_utc(conn):
    insert_reading(conn, make_reading(timestamp=at(9)))
    insert_reading(conn, make_reading(timestamp=at(10)))
    istanbul = timezone(timedelta(hours=3))

    rows = fetch_latest(conn, since=datetime(2026, 11, 27, 13, tzinfo=istanbul))

    assert [row["timestamp"] for row in rows] == [at(10)]


def test_time_filters_without_time_zone_are_rejected(conn):
    with pytest.raises(ValueError, match="time zone"):
        fetch_latest(conn, since=datetime(2026, 11, 27, 10))


def test_device_filter_is_a_parameter_not_sql(conn):
    insert_reading(conn, make_reading())

    rows = fetch_latest(conn, device_id="x' OR '1'='1")

    assert rows == []
    assert len(fetch_latest(conn)) == 1


def test_list_devices_returns_count_and_time_range(conn):
    insert_reading(conn, make_reading(device_id="MOTOR-002", timestamp=at(9)))
    insert_reading(conn, make_reading(device_id="MOTOR-001", timestamp=at(10)))
    insert_reading(conn, make_reading(device_id="MOTOR-001", timestamp=at(12)))

    assert list_devices(conn) == [
        {"device_id": "MOTOR-001", "reading_count": 2, "first_seen": at(10), "last_seen": at(12)},
        {"device_id": "MOTOR-002", "reading_count": 1, "first_seen": at(9), "last_seen": at(9)},
    ]


def test_list_devices_is_empty_without_readings(conn):
    assert list_devices(conn) == []


def test_latest_per_device_returns_newest_reading_of_each_device(conn):
    insert_reading(conn, make_reading(device_id="MOTOR-001", timestamp=at(12), temperature=1))
    insert_reading(conn, make_reading(device_id="MOTOR-001", timestamp=at(10), temperature=2))
    insert_reading(conn, make_reading(device_id="MOTOR-002", timestamp=at(9), temperature=3))

    rows = latest_per_device(conn)

    assert [(row["device_id"], row["temperature"]) for row in rows] == [
        ("MOTOR-001", 1.0),
        ("MOTOR-002", 3.0),
    ]
    assert "position" not in rows[0]


def test_reading_stats_computes_min_avg_max_per_device(conn):
    for temperature in (20.0, 30.0, 40.0):
        insert_reading(conn, make_reading(device_id="MOTOR-001", temperature=temperature))
    insert_reading(conn, make_reading(device_id="MOTOR-002", temperature=90.0))

    stats = reading_stats(conn)

    assert [row["device_id"] for row in stats] == ["MOTOR-001", "MOTOR-002"]
    first = stats[0]
    assert first["reading_count"] == 3
    assert (first["temperature_min"], first["temperature_avg"], first["temperature_max"]) == (
        20.0,
        30.0,
        40.0,
    )
    assert first["humidity_avg"] == 50.0


def test_reading_stats_respects_device_and_time_filters(conn):
    insert_reading(conn, make_reading(device_id="MOTOR-001", timestamp=at(9), temperature=10))
    insert_reading(conn, make_reading(device_id="MOTOR-001", timestamp=at(11), temperature=50))
    insert_reading(conn, make_reading(device_id="MOTOR-002", timestamp=at(11), temperature=70))

    stats = reading_stats(conn, device_id="MOTOR-001", since=datetime(2026, 11, 27, 10, tzinfo=UTC))

    assert len(stats) == 1
    assert stats[0]["reading_count"] == 1
    assert stats[0]["temperature_max"] == 50.0


def test_connection_can_be_shared_with_another_thread_when_allowed(tmp_path):
    path = str(tmp_path / "sensors.db")
    strict = connect(path)
    shared = connect(path, check_same_thread=False)
    errors = {}

    def use(name, connection):
        try:
            list_devices(connection)
        except sqlite3.ProgrammingError as error:
            errors[name] = error

    for name, connection in (("strict", strict), ("shared", shared)):
        thread = threading.Thread(target=use, args=(name, connection))
        thread.start()
        thread.join()
    strict.close()
    shared.close()

    assert set(errors) == {"strict"}
