import logging
from os import environ

import paho.mqtt.client as mqtt


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    logging.info(f"Connected with result code {reason_code}")
    
    topics = [
        ('/devices/UD12/controls/K1', 0),
        ('/devices/UD12/controls/K2', 0),
        ('/devices/UD12/controls/K3', 0),
        ('/devices/UD12/controls/K4', 0),
        ('/devices/UD12/controls/Channel 1', 0),
        ('/devices/UD12/controls/Channel 2', 0),
        ('/devices/UD12/controls/Channel 3', 0),
        ('/devices/UD12/controls/Channel 4', 0),
        ('/devices/rgbw/UD12/state/set', 0),
        ('/devices/rgbw/UD12/rgbw/set', 0)
    ]
    client.subscribe(topics)

#       1 2 3 4
# MAP = w r b g
#       R G B W

CHANNEL_MAP = {
    'Channel 1': 3,
    'Channel 2': 0,
    'Channel 3': 2,
    'Channel 4': 1
}

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    logging.info(f"Received message on {topic}: {payload}")
    
    if topic in ['/devices/UD12/controls/K1', '/devices/UD12/controls/K2', '/devices/UD12/controls/K3', '/devices/UD12/controls/K4']:
        k_key = topic.split('/')[-1]
        userdata["k_values"][k_key] = int(payload)
        state = "on" if all(userdata["k_values"].values()) else "off"
        client.publish('/devices/rgbw/UD12/state', state)
        
    elif topic in ['/devices/UD12/controls/Channel 1', '/devices/UD12/controls/Channel 2', '/devices/UD12/controls/Channel 3', '/devices/UD12/controls/Channel 4']:
        channel_key = topic.split('/')[-1]
        userdata["channel_values"][channel_key] = int(payload)
       
        rgbw_values = [0] * 4
        for ch, index in CHANNEL_MAP.items():
            rgbw_values[index] = str((userdata["channel_values"][ch] * 255) // 1000)
        
        client.publish('/devices/rgbw/UD12/rgbw', ",".join(rgbw_values))
        
    elif topic == '/devices/rgbw/UD12/state/set':
        payload = "1" if payload == "on" else "0"
        if payload == userdata["state"]:
            return
        
        userdata["state"] = payload
        client.publish('/devices/UD12/controls/K1/on', payload)
        client.publish('/devices/UD12/controls/K2/on', payload)
        client.publish('/devices/UD12/controls/K3/on', payload)
        client.publish('/devices/UD12/controls/K4/on', payload)

    elif topic == '/devices/rgbw/UD12/rgbw/set':
        # scale 255 to 1000
        rgbw_values = [(int(v) * 1000) // 255  for v in payload.split(',')]
    
        for i, value in enumerate(rgbw_values, 1):
            value = rgbw_values[CHANNEL_MAP[f'Channel {i}']]
            client.publish(f'/devices/UD12/controls/Channel {i}/on', value)


def on_disconnect(client, userdata, rc):
    logging.info(f"Disconnected with result code {rc}")


def main():
    log_level = environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(level=log_level)
    
    userdata = {
        'state': None,
        'k_values': {'K1': 0, 'K2': 0, 'K3': 0, 'K4': 0},
        'channel_values': {'Channel 1': 0, 'Channel 2': 0, 'Channel 3': 0, 'Channel 4': 0}
    }
    
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=userdata)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_disconnect = on_disconnect

    host = environ.get("MQTT_HOST")
    port = int(environ.get("MQTT_PORT", 1883))
    logging.info(f"Connecting to {host}:{port}")
    mqttc.connect(host, port, keepalive=60)

    topic = environ.get("MQTT_TOPIC", "/devices/rgbw/ud12")
    mqttc.subscribe(topic)

    mqttc.loop_forever()


if __name__ == '__main__':
    main()