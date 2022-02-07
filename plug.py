import paho.mqtt.client as mqtt
import time
from datetime import datetime
import robonomicsinterface as RI
import json
import os
import typing as tp
import yaml
import logging

SENDING_TIMEOUT = 3000 # sec
BROCKER_ADDRESS = "localhost"
BROCKER_PORT = 1883

class PlugMonitoring:
    def __init__(self) -> None:
        self.path = os.path.realpath(__file__)[:-len(__file__)]
        self.prev_time = time.time()
        self.prev_time_sending = time.time()
        # Чтение конфига (сид от датчика)
        self.plug_seed = ""
        # Создание твина если его нет
        # Список топиков
        topics = self.read_topics()
        self.client = mqtt.Client()
        self.client.connect(BROCKER_ADDRESS, BROCKER_PORT, 60)
        self.client.subscribe(topics)
        self.client.on_message = self.on_message

    def send_datalog(self, data: str) -> None:
        interface = RI.RobonomicsInterface(seed=self.plug_seed)
        interface.record_datalog(data)

    def on_message(self, client: mqtt.Client, userdata: None, message: mqtt.MQTTMessage) -> None:
        data = str(message.payload.decode())
        data = json.loads(data)
        energy = self.write_usage(data["power"])
        if (time.time() - self.prev_time_sending) > SENDING_TIMEOUT:
            self.send_datalog(str(energy))

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
        print(f"config: {config}")
        for device in config["devices"]:
            topic = config["devices"][device]["friendly_name"]
            topic = f"zigbee2mqtt/{topic}"
            topics.append((topic, 1))
        return topics

    
    def spin(self) -> None:
        self.client.loop_forever()

if __name__ == '__main__':
    PlugMonitoring().spin()
