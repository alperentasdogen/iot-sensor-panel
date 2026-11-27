import pytest

from storage.database import connect, fetch_latest, insert_reading


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
