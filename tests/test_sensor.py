from simulator.sensor import generate_sensor_data


def test_sensor_data_ranges():
    data = generate_sensor_data()

    assert data["device_id"] == "MOTOR-001"
    assert 25 <= data["temperature"] <= 85
    assert 30 <= data["humidity"] <= 70
    assert 0 <= data["vibration"] <= 10
    assert 2 <= data["current"] <= 15


def test_sensor_data_fields():
    data = generate_sensor_data()

    expected_fields = {
        "device_id",
        "timestamp",
        "temperature",
        "humidity",
        "vibration",
        "current",
    }

    assert set(data.keys()) == expected_fields
