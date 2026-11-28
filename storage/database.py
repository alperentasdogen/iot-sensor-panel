"""SQLite storage for sensor readings."""

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

MEASUREMENT_FIELDS = ("temperature", "humidity", "vibration", "current")

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,
    temperature REAL    NOT NULL,
    humidity    REAL    NOT NULL,
    vibration   REAL    NOT NULL,
    current     REAL    NOT NULL,
    received_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_device_time ON readings (device_id, timestamp);
"""


# The queries below are fixed strings. Optional filters use the
# "(:value IS NULL OR column = :value)" pattern, so user input only ever
# reaches SQLite as a bound parameter and no SQL is built at runtime.
SELECT_READINGS = """
SELECT * FROM readings
WHERE (:device_id IS NULL OR device_id = :device_id)
  AND (:since IS NULL OR timestamp >= :since)
  AND (:until IS NULL OR timestamp <= :until)
ORDER BY timestamp DESC, id DESC
LIMIT :limit
"""

SELECT_DEVICES = """
SELECT device_id,
       COUNT(*)       AS reading_count,
       MIN(timestamp) AS first_seen,
       MAX(timestamp) AS last_seen
FROM readings
GROUP BY device_id
ORDER BY device_id
"""

SELECT_LATEST_PER_DEVICE = """
SELECT id, device_id, timestamp, temperature, humidity, vibration, current, received_at
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY device_id ORDER BY timestamp DESC, id DESC
    ) AS position
    FROM readings
)
WHERE position = 1
ORDER BY device_id
"""

SELECT_STATS = """
SELECT device_id,
       COUNT(*)         AS reading_count,
       MIN(temperature) AS temperature_min,
       AVG(temperature) AS temperature_avg,
       MAX(temperature) AS temperature_max,
       MIN(humidity)    AS humidity_min,
       AVG(humidity)    AS humidity_avg,
       MAX(humidity)    AS humidity_max,
       MIN(vibration)   AS vibration_min,
       AVG(vibration)   AS vibration_avg,
       MAX(vibration)   AS vibration_max,
       MIN(current)     AS current_min,
       AVG(current)     AS current_avg,
       MAX(current)     AS current_max
FROM readings
WHERE (:device_id IS NULL OR device_id = :device_id)
  AND (:since IS NULL OR timestamp >= :since)
  AND (:until IS NULL OR timestamp <= :until)
GROUP BY device_id
ORDER BY device_id
"""


def connect(path: str, *, check_same_thread: bool = True) -> sqlite3.Connection:
    """Open the database at path, creating its folder and the schema if needed.

    Pass check_same_thread=False only when one connection is handed between
    threads but never used by two threads at once (e.g. per-request API use).
    """
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_reading(conn: sqlite3.Connection, reading: Mapping[str, object]) -> int:
    """Store one validated reading and return its row id."""
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO readings
                (device_id, timestamp, temperature, humidity, vibration, current, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reading["device_id"],
                reading["timestamp"],
                *(reading[field] for field in MEASUREMENT_FIELDS),
                datetime.now(UTC).isoformat(),
            ),
        )
    return cursor.lastrowid


def _to_utc_text(moment: datetime | None) -> str | None:
    """Convert a time-zone aware datetime to the UTC ISO text stored in the table."""
    if moment is None:
        return None
    if moment.tzinfo is None:
        raise ValueError("datetime filters must include a time zone")
    return moment.astimezone(UTC).isoformat()


def _filters(
    device_id: str | None, since: datetime | None, until: datetime | None
) -> dict[str, object]:
    return {"device_id": device_id, "since": _to_utc_text(since), "until": _to_utc_text(until)}


def fetch_latest(
    conn: sqlite3.Connection,
    limit: int = 100,
    device_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict]:
    """Return up to limit readings, newest first.

    Readings can be narrowed to one device and to a time range (inclusive).
    """
    if limit < 1:
        raise ValueError(f"limit must be positive, got {limit}")
    params = {**_filters(device_id, since, until), "limit": limit}
    return [dict(row) for row in conn.execute(SELECT_READINGS, params)]


def list_devices(conn: sqlite3.Connection) -> list[dict]:
    """Return every device that sent readings, with its count and first/last time."""
    return [dict(row) for row in conn.execute(SELECT_DEVICES)]


def latest_per_device(conn: sqlite3.Connection) -> list[dict]:
    """Return the newest reading of each device."""
    return [dict(row) for row in conn.execute(SELECT_LATEST_PER_DEVICE)]


def reading_stats(
    conn: sqlite3.Connection,
    device_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict]:
    """Return per-device count and min/avg/max of each measurement.

    Columns are named <measurement>_min, <measurement>_avg and <measurement>_max.
    """
    return [dict(row) for row in conn.execute(SELECT_STATS, _filters(device_id, since, until))]
