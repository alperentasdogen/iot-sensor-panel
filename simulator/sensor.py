import random
from datetime import UTC, datetime

DEFAULT_DEVICE_ID = "MOTOR-001"


def generate_sensor_data(device_id: str = DEFAULT_DEVICE_ID) -> dict[str, str | float]:
    """Return one simulated sensor reading for the given device."""
    return {
        "device_id": device_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "temperature": round(random.uniform(25, 85), 2),
        "humidity": round(random.uniform(30, 70), 2),
        "vibration": round(random.uniform(0, 10), 2),
        "current": round(random.uniform(2, 15), 2),
    }


if __name__ == "__main__":
    print(generate_sensor_data())
