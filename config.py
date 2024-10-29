from os import environ


MQTT_HOST = environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(environ.get("MQTT_PORT", 1883))
LOG_LEVEL = environ.get("LOG_LEVEL", "INFO").upper()

DEVICE_CONFIGS = [
    {
        "name": "UD12",
        "type": "RazumdomRGBW",
        "channels": {
            "R": 2,
            "G": 4,
            "B": 1,
            "W": 3,
        }
    },
    {
        "name": "UD11",
        "type": "RazumdomRGBW",
        "channels": {
            "R": 2,
            "G": 4,
            "B": 1,
            "W": 3,
        }
    },
]