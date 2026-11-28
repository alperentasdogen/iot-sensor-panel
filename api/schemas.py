"""Response models of the REST API. FastAPI also uses them for the /docs page."""

from datetime import datetime

from pydantic import BaseModel


class Health(BaseModel):
    status: str
    database: str


class Device(BaseModel):
    device_id: str
    reading_count: int
    first_seen: datetime
    last_seen: datetime


class Reading(BaseModel):
    id: int
    device_id: str
    timestamp: datetime
    temperature: float
    humidity: float
    vibration: float
    current: float
    received_at: datetime


class MeasurementStats(BaseModel):
    min: float
    avg: float
    max: float


class DeviceStats(BaseModel):
    device_id: str
    reading_count: int
    temperature: MeasurementStats
    humidity: MeasurementStats
    vibration: MeasurementStats
    current: MeasurementStats
