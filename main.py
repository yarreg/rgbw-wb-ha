import logging
from os import environ

import paho.mqtt.client as mqtt


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    logging.info(f"Connected with result code {reason_code}")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    logging.info(msg.topic+" "+ str(msg.payload))


def on_disconnect(client, userdata, rc):
    logging.info(f"Disconnected with result code {rc}")


def main():
    log_level = environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(level=log_level)
    
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_disconnect = on_disconnect

    host = environ.get("MQTT_HOST")
    port = int(environ.get("MQTT_PORT", 1883))
    mqttc.connect(host, port, 60)

    topic = environ.get("MQTT_TOPIC", "/devices/rgbw/ud12")
    mqttc.subscribe(topic)

    mqttc.loop_forever()


if __name__ == '__main__':
    main()