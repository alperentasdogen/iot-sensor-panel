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


def connect(path: str) -> sqlite3.Connection:
    """Open the database at path, creating its folder and the schema if needed."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
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


def fetch_latest(
    conn: sqlite3.Connection, limit: int = 100, device_id: str | None = None
) -> list[dict]:
    """Return up to limit readings, newest first, optionally for a single device."""
    if limit < 1:
        raise ValueError(f"limit must be positive, got {limit}")
    query = "SELECT * FROM readings"
    params: list[object] = []
    if device_id is not None:
        query += " WHERE device_id = ?"
        params.append(device_id)
    query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
    params.append(limit)
    return [dict(row) for row in conn.execute(query, params)]
