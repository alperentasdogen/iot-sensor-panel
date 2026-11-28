"""Entry point of the REST API: python -m api.main (or uvicorn api.main:app)."""

import uvicorn

from api.app import create_app
from config import load_settings

# Listen on this machine only, like the MQTT broker.
API_HOST = "127.0.0.1"
API_PORT = 8000

app = create_app(load_settings().database_path)


if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT)
