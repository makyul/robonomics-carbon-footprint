import paho.mqtt.client as mqtt
import time
import robonomicsinterface as RI
import json
import os
import typing as tp
import yaml
import configparser
from substrateinterface import Keypair
import os

SENDING_TIMEOUT = 20 # sec
BROCKER_ADDRESS = "localhost"
BROCKER_PORT = 1883

class PlugMonitoring:
    def __init__(self) -> None:
        self.path = os.path.realpath(__file__)[:-len(__file__)]
        self.prev_time = time.time()
        self.prev_time_sending = time.time()
        config = self.read_config(f"{self.path}config/config.yaml")
        self.location = config["location"]
        self.plug_seed = config["device_seed"]
        self.service_address = config["service_address"]
        topics = self.read_topics()
        self.client = mqtt.Client()
        self.client.connect(BROCKER_ADDRESS, BROCKER_PORT, 60)
        self.client.subscribe(topics)
        self.client.on_message = self.on_message

    def send_launch(self):
        print(f"Sending launch to add topic")
        interface = RI.RobonomicsInterface(seed=self.plug_seed)
        hash = interface.send_launch(self.service_address)
        print(f"Launch created with hash {hash}")

    def send_datalog(self, data: str) -> None:
        print(f"Sending datalog with data {data}")
        interface = RI.RobonomicsInterface(seed=self.plug_seed)
        hash = interface.record_datalog(data)
        print(f"Datalog created with hash {hash}")

    def on_message(self, client: mqtt.Client, userdata: None, message: mqtt.MQTTMessage) -> None:
        data = str(message.payload.decode())
        data = json.loads(data)
        energy = self.write_usage(data["power"])
        print(f"Got mqtt message {data}")
        if (time.time() - self.prev_time_sending) > SENDING_TIMEOUT:
            text = {"geo": self.location, "power_usage": energy, "timestamp": time.time()}
            self.send_datalog(str(text))

    def write_usage(self, power: float) -> float:
        try:
            with open(f"{self.path}data/energy", "r") as f_energy:
                energy = float(f_energy.readline())
        except FileNotFoundError:
            energy = 0
        now_time = time.time()
        delta_time = now_time - self.prev_time
        self.prev_time = now_time
        energy += power*(delta_time/3600)
        with open(f"{self.path}data/energy", "w") as f_energy:
            f_energy.write(str(energy))
        return energy

    def read_topics(self) -> tp.List[tp.Tuple[str, int]]:
        with open("/opt/zigbee2mqtt/data/configuration.yaml", "r") as config_file:
            config = yaml.safe_load(config_file)
        topics = []
        for device in config["devices"]:
            topic = config["devices"][device]["friendly_name"]
            topic = f"zigbee2mqtt/{topic}"
            topics.append((topic, 1))
        print(f"Topics to subscribe {topics}")
        return topics

    def read_config(self, path: str):
        with open(path) as f:
            config_file = yaml.safe_load(f)
        if "device_seed" not in config_file:
            mnemonic = Keypair.generate_mnemonic()
            print(f"Generated account with address: {Keypair.create_from_mnemonic(mnemonic, ss58_format=32)}")
            config_file["device_address"] = mnemonic
            with open(path, "w") as f:
                yaml.dump(config_file, f)
        if "location" not in config_file:
            config_file["location"] = os.environ["LOCATION"]
            with open(path, "w") as f:
                yaml.dump(config_file, f)
        return config_file
    
    def spin(self) -> None:
        self.client.loop_forever()

if __name__ == '__main__':
    PlugMonitoring().spin()

