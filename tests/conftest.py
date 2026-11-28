import paho.mqtt.client as mqtt
import pytest


@pytest.fixture
def client_kwargs(monkeypatch):
    """Record the keyword arguments of every paho Client created during the test.

    paho keeps the client id in a private attribute, so tests check what was
    passed to the constructor instead of reading the client's internals.
    """
    calls = []
    real_client = mqtt.Client

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(mqtt, "Client", spy)
    return calls
