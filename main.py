#!/usr/bin/env python

import logging
import json
from typing import Callable

import paho.mqtt.client as mqtt

import config


class Device:
    def __init__(self, client: mqtt.Client, name: str) -> None:
        self.client = client
        self.name = name
        self._update_callbacks: list[Callable] = []

    def add_update_callback(self, callback: Callable) -> None:
        """Add a callback to be executed when the device state updates."""
        self._update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable) -> None:
        """Remove a previously added update callback."""
        self._update_callbacks.remove(callback)

    def _execute_callbacks(self) -> None:
        """Execute all registered update callbacks."""
        for fn in self._update_callbacks:
            fn(self)

    def process_message(self, topic: str, payload: str) -> None:
        """Process incoming MQTT message."""
        pass


class RazumdomRGBW(Device):
    """Represents a Razumdom RGBW device controlled via MQTT."""

    def __init__(self, client: mqtt.Client, name: str, channels: dict[str, int], **kwargs) -> None:
        super().__init__(client, name)
        self.channels = channels  # Custom channel mappings

        self.state = {
            "k_values": {f"K{i}": 0 for i in range(1, 5)},
            "channel_values": {f"Channel {i}": 0 for i in range(1, 5)},
        }

        # Subscribe to device-specific topics
        for i in range(1, 5):
            self.client.message_callback_add(
                f"/devices/{self.name}/controls/Channel {i}",
                lambda c, u, m: self.process_message(m.topic, m.payload.decode("utf-8")),
            )
            self.client.message_callback_add(
                f"/devices/{self.name}/controls/K{i}",
                lambda c, u, m: self.process_message(m.topic, m.payload.decode("utf-8")),
            )

    def process_message(self, topic: str, payload: str) -> None:
        """Handle incoming MQTT messages."""
        try:
            logging.debug(f"Received message: {topic} - {payload}")

            last_topic = topic.split("/")[-1]
            if last_topic.startswith("K"):
                self.state["k_values"][last_topic] = int(payload)
            elif last_topic.startswith("Channel"):
                self.state["channel_values"][last_topic] = int(payload)
            else:
                logging.warning(f"Unknown topic: {topic}")
                return

            self._execute_callbacks()
        except Exception as e:
            logging.exception(f"Error processing message {topic}: {e}")

    @property
    def is_on(self) -> bool:
        """Check if the device is turned on."""
        return all(value > 0 for value in self.state["k_values"].values())

    @is_on.setter
    def is_on(self, value: bool) -> None:
        """Turn the device on or off."""
        state_str = str(int(value))
        for i in range(1, 5):
            self.client.publish(f"/devices/{self.name}/controls/K{i}/on", state_str)

    @property
    def rgbw(self) -> list[int]:
        """Get the current RGBW values."""
        rgbw_values = []
        for color in ["R", "G", "B", "W"]:
            channel_num = self.channels.get(color)
            channel_value = self.state["channel_values"].get(f"Channel {channel_num}", 0)
            rgbw_values.append(round(channel_value * 255 / 1000))
        return rgbw_values

    @rgbw.setter
    def rgbw(self, values: list[int]) -> None:
        """Set the RGBW values."""
        for i, color in enumerate(["R", "G", "B", "W"]):
            channel_num = self.channels.get(color)
            value = round(values[i] * 1000 / 255)
            self.client.publish(f"/devices/{self.name}/controls/Channel {channel_num}/on", value)

    @property
    def brightness(self) -> int:
        """Get the brightness level."""
        return round(sum(self.rgbw) / 4)

    @brightness.setter
    def brightness(self, value: int) -> None:
        """Set the brightness level."""
        self.rgbw = [value] * 4


class DeviceManager:
    """Main application class."""

    def __init__(self, mqtt_host: str, mqtt_port: int) -> None:
        # Configure MQTT client
        self._mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._mqttc.on_connect = self._on_mqtt_connect
        self._mqttc.on_disconnect = self._on_mqtt_disconnect
        self._mqttc.connect(mqtt_host, mqtt_port, keepalive=60)

        # Initialize devices
        self._devices: dict[str, Device] = {}

    def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties) -> None:
        """Handle MQTT connection event."""
        logging.info("Connected to MQTT broker")
        for device in self._devices.values():
            self._mqttc.subscribe(f"/devices/{device.name}/#")

    def _on_mqtt_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        """Handle MQTT disconnection event."""
        logging.warning(f"Disconnected from MQTT broker with code: {reason_code}")

    def add_device(self, device_config: dict) -> None:
        """Add a new device based on configuration."""
        try:
            device_type = device_config["type"]
            name = device_config["name"]
            channels = device_config.get("channels", {})

            if device_type == "RazumdomRGBW":
                device = RazumdomRGBW(self._mqttc, name, channels)
                device.add_update_callback(self._on_device_update)
                self._devices[name] = device

                # Subscribe to set commands
                self._mqttc.message_callback_add(
                    f"/devices/{name}/rgbw/set", lambda c, u, m: self._handle_set_command(name, m)
                )
            else:
                logging.error(f"Unknown device type: {device_type}")
        except KeyError as e:
            logging.error(f"Missing required configuration key: {e}")
        except Exception as e:
            logging.exception(f"Error adding device: {e}")

    def _handle_set_command(self, device_name: str, message: mqtt.MQTTMessage) -> None:
        """Handle incoming set commands."""
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            device = self._devices.get(device_name)
            if not device or not isinstance(device, RazumdomRGBW):
                return

            state = payload.get("state")
            if state == "OFF":
                device.is_on = False
                return

            if state == "ON" and not device.is_on:
                device.is_on = True

            color = payload.get("color")
            brightness = payload.get("brightness")

            if brightness is not None and color is None:
                device.brightness = brightness
                return

            if color:
                rgbw_values = [color.get(k, 0) for k in ["r", "g", "b", "w"]]
                device.rgbw = rgbw_values

        except json.JSONDecodeError:
            logging.error(f"Invalid JSON payload: {message.payload}")
        except Exception as e:
            logging.exception(f"Error handling set command: {e}")

    def _on_device_update(self, device: Device) -> None:
        """Handle device updates."""
        if isinstance(device, RazumdomRGBW):
            message = {
                "state": "ON" if device.is_on else "OFF",
                "color": dict(zip(["r", "g", "b", "w"], device.rgbw)),
                "color_mode": "rgbw",
                "brightness": device.brightness,
            }
            logging.debug(f"Publishing state for device {device.name}: {message}")
            self._mqttc.publish(f"/devices/{device.name}/rgbw", json.dumps(message))
        else:
            raise NotImplementedError(f"Update handler for {type(device)} is not implemented")

    def run(self) -> None:
        """Start the MQTT client loop."""
        try:
            self._mqttc.loop_forever()
        except KeyboardInterrupt:
            logging.info("Application stopped by user")
            self._mqttc.disconnect()
        except Exception as e:
            logging.exception(f"An unexpected error occurred: {e}")
            self._mqttc.disconnect()


def main():
    logging.basicConfig(level=config.LOG_LEVEL)

    manager = DeviceManager(config.MQTT_HOST, config.MQTT_PORT)
    for device_config in config.DEVICE_CONFIGS:
        manager.add_device(device_config)
    manager.run()


if __name__ == "__main__":
    main()
