"""REST API that serves the sensor readings stored by the subscriber.

The API only reads the database; the subscriber is the only writer.
"""

import logging
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status

from api.schemas import Device, DeviceStats, Health, MeasurementStats, Reading
from storage.database import (
    MEASUREMENT_FIELDS,
    connect,
    fetch_latest,
    latest_per_device,
    list_devices,
    reading_stats,
)

logger = logging.getLogger(__name__)

DEVICE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

DeviceIdQuery = Annotated[
    str | None,
    Query(pattern=DEVICE_ID_PATTERN, description="Only this device, e.g. MOTOR-001"),
]
SinceQuery = Annotated[
    datetime | None,
    Query(
        description="Start of the time range (inclusive), with time zone, e.g. 2026-11-28T10:00:00Z"
    ),
]
UntilQuery = Annotated[
    datetime | None,
    Query(description="End of the time range (inclusive), with time zone"),
]


def get_connection(request: Request) -> Iterator[sqlite3.Connection]:
    """Open one database connection per request and close it afterwards.

    FastAPI may run the dependency and the endpoint in different worker
    threads, so the connection allows cross-thread use. It is never shared
    between requests, so two threads never use it at the same time.
    """
    try:
        conn = connect(request.app.state.database_path, check_same_thread=False)
    except sqlite3.Error as error:
        logger.error("Cannot open database: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from error
    try:
        yield conn
    finally:
        conn.close()


Connection = Annotated[sqlite3.Connection, Depends(get_connection)]


def check_time_range(since: datetime | None, until: datetime | None) -> None:
    for name, value in (("since", since), ("until", until)):
        if value is not None and value.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{name} must include a time zone, e.g. 2026-11-28T10:00:00Z",
            )
    if since is not None and until is not None and since > until:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="since must not be later than until",
        )


def to_device_stats(row: dict) -> DeviceStats:
    measurements = {
        field: MeasurementStats(
            min=row[f"{field}_min"], avg=row[f"{field}_avg"], max=row[f"{field}_max"]
        )
        for field in MEASUREMENT_FIELDS
    }
    return DeviceStats(
        device_id=row["device_id"], reading_count=row["reading_count"], **measurements
    )


def create_app(database_path: str) -> FastAPI:
    """Create the API for the SQLite database at database_path."""
    app = FastAPI(
        title="IoT Sensor Panel API",
        description="Read-only access to the sensor readings collected over MQTT.",
        version="0.3.0",
    )
    app.state.database_path = database_path

    @app.get("/health", tags=["system"])
    def health(conn: Connection) -> Health:
        """Report whether the API is running and the database can be read."""
        conn.execute("SELECT 1")
        return Health(status="ok", database="ok")

    @app.get("/devices", tags=["devices"])
    def devices(conn: Connection) -> list[Device]:
        """List every device that has sent readings."""
        return [Device(**row) for row in list_devices(conn)]

    @app.get("/readings/latest", tags=["readings"])
    def latest_readings(conn: Connection) -> list[Reading]:
        """Return the newest reading of each device."""
        return [Reading(**row) for row in latest_per_device(conn)]

    @app.get("/readings", tags=["readings"])
    def readings(
        conn: Connection,
        device_id: DeviceIdQuery = None,
        since: SinceQuery = None,
        until: UntilQuery = None,
        limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    ) -> list[Reading]:
        """Return readings newest first, optionally for one device and a time range."""
        check_time_range(since, until)
        rows = fetch_latest(conn, limit=limit, device_id=device_id, since=since, until=until)
        return [Reading(**row) for row in rows]

    @app.get("/stats", tags=["readings"])
    def stats(
        conn: Connection,
        device_id: DeviceIdQuery = None,
        since: SinceQuery = None,
        until: UntilQuery = None,
    ) -> list[DeviceStats]:
        """Return per-device count and min/avg/max of each measurement."""
        check_time_range(since, until)
        rows = reading_stats(conn, device_id=device_id, since=since, until=until)
        return [to_device_stats(row) for row in rows]

    return app
