import logging
import json
from os import environ

import paho.mqtt.client as mqtt


class RazumdomRGBW:
    def __init__(self, client, name, r_ch=1, g_ch=2, b_ch=3, w_ch=4) -> None:
        self.client = client
        self.name = name
        self.channels = {
            'R': r_ch,
            'G': g_ch,
            'B': b_ch,
            'W': w_ch
        }
        
        self.update_callbacks = []
        
        self.state = {
            'k_values': {'K1': 0, 'K2': 0, 'K3': 0, 'K4': 0},
            'channel_values': {'Channel 1': 0, 'Channel 2': 0, 'Channel 3': 0, 'Channel 4': 0}
        }
        
        for i in range(1, 5):
            self.client.message_callback_add(f'/devices/{self.name}/controls/Channel {i}', self._on_mqtt_message)
            self.client.message_callback_add(f'/devices/{self.name}/controls/K{i}', self._on_mqtt_message)
        
    def execute_callbacks(self):
        for fn in self.update_callbacks:
            fn(self)
        
    def _on_mqtt_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        logging.info(f"Received message: {topic} - {payload}")

        last_topic = topic.split('/')[-1]
        if last_topic in ('K1', 'K2', 'K3', 'K4'):
            self.state["k_values"][last_topic] = int(payload)
            self.execute_callbacks()
        elif last_topic in ('Channel 1', 'Channel 2', 'Channel 3', 'Channel 4'):
            self.state["channel_values"][last_topic] = int(payload)
            self.execute_callbacks()
        else:
            logging.error(f"Unknown topic: {topic}")
      
    def set_rgbw(self, rgbw):
        for i, key in enumerate(["R", "G", "B", "W"]):
            ch = self.channels[key]
            value = round(rgbw[i] * 1000 / 255)
            self.client.publish(f'/devices/{self.name}/controls/Channel {ch}/on', value)
        
    def set_state(self, state):
        state = str(int(state))
        for i in range(1, 5):
            self.client.publish(f'/devices/{self.name}/controls/K{i}/on', state)
            
    def get_brightness(self):
        return round(sum(self.get_rgbw()) / 4)
    
    def set_brightness(self, brightness):
        rgbw = [brightness] * 4
        self.set_rgbw(rgbw)
            
    def get_state(self):
        return all(self.state['k_values'].values())
    
    def get_rgbw(self):
        rgbw_values = [0] * 4
        for i, key in enumerate(["R", "G", "B", "W"]):
            ch = self.channels[key]
            rgbw_values[i] = round(self.state['channel_values'][f'Channel {ch}'] * 255 / 1000)
            
        return rgbw_values


class App:
    def __init__(self, mqtt_host, mqtt_port) -> None:
        self.mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=None)
        
        logging.info(f"Connecting to {mqtt_host}:{mqtt_port}")
        self.mqttc.connect(mqtt_host, mqtt_port, keepalive=60)
        self.mqttc.on_disconnect = self.on_mqtt_disconnect
        self.mqttc.on_connect = self.on_mqtt_connect
        #self.mqttc.on_message = self.on_mqtt_message
        
        self.mqttc.subscribe("/devices/UD12/#")
        self.razumdom_rgbw_ud12 = RazumdomRGBW(self.mqttc , 'UD12', 2, 4, 1, 3)
        self.razumdom_rgbw_ud12.update_callbacks.append(self.on_razumdom_update)
        self.mqttc.message_callback_add("/devices/UD12/rgbw/set", self.on_set_rgbw)
        
    def on_razumdom_update(self, razumdom_rgbw):
        message = {
            "state": "ON" if razumdom_rgbw.get_state() else "OFF",
            "color": {k: v for k, v in zip(["r", "g", "b", "w"], razumdom_rgbw.get_rgbw())},
            "color_mode": "rgbw",
            "brightness": razumdom_rgbw.get_brightness(),
        }
        logging.info(message)
        self.mqttc.publish('/devices/UD12/rgbw', json.dumps(message))
        
    def on_set_rgbw(self, client, userdata, msg):
        topic = msg.topic
        payload = json.loads(msg.payload.decode('utf-8'))
        logging.info(f"Received message: {topic} - {payload}")
        
        """
        Response example:
        {
            "state": "ON",
            "color": {
                "r": 255,
                "g": 255,
                "b": 255,
                "w": 255
            },
            "color_mode": "rgbw",
            "brightness": 100
        }
        """
        
        if payload["state"] == "OFF":
            self.razumdom_rgbw_ud12.set_state(False)
            return
        
        if payload["state"] == "ON" and not self.razumdom_rgbw_ud12.get_state():
            self.razumdom_rgbw_ud12.set_state(True)

        color = payload.get('color')
        brightness = payload.get('brightness')
        
        if brightness and not color:
            self.razumdom_rgbw_ud12.set_brightness(brightness)
            return
        
        if color:
            self.razumdom_rgbw_ud12.set_rgbw([color["r"], color["g"], color["b"], color["w"]])
            return
        
    def on_mqtt_message(self, client, userdata, msg):
      pass

    def on_mqtt_disconnect(self, client, userdata, rc):
        logging.info(f"Disconnected with result code {rc}")
        
    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        logging.info(f"Connected with result code {reason_code}")

    def run(self):
        self.mqttc.loop_forever()


def main():
    log_level = environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(level=log_level)
    

    host = environ.get("MQTT_HOST")
    port = int(environ.get("MQTT_PORT", 1883))

    app = App(host, port)
    app.run()

if __name__ == '__main__':
    main()