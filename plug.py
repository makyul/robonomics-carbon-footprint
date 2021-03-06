import paho.mqtt.client as mqtt
import time
import robonomicsinterface as RI
import json
import os
import typing as tp
import yaml
from substrateinterface import Keypair
import logging
import threading

logger = logging.getLogger(__name__)
logger.propagate = False
handler = logging.StreamHandler()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class PlugMonitoring:
    def __init__(self) -> None:
        self.path = os.path.realpath(__file__)[:-len(__file__)]
        self.prev_time = time.time()
        self.prev_time_sending = time.time()
        self.config = self.read_config(f"{self.path}config/config.yaml")
        self.location = self.config["location"]
        self.plug_seed = self.config["device_seed"]
        self.service_address = self.config["service_address"]
        self.check_balance()
        self.send_launch()
        topics = self.read_topics()
        self.client = mqtt.Client()
        self.client.connect(self.config['broker_address'], self.config['broker_port'], 60)
        self.client.subscribe(topics)
        self.client.on_message = self.on_message

    def check_balance(self) -> None:
        interface = RI.RobonomicsInterface(seed=self.plug_seed)
        info = interface.custom_chainstate("System", "Account", interface.define_address())
        if info.value['data']['free'] > 0:
            logger.info(f"Balance is OK")
            balance = True
        else:
            logger.info(f"Waiting fot tokens on account balance")
            balance = False
        while not balance:
            info = interface.custom_chainstate("System", "Account", interface.define_address())
            if info.value['data']['free'] > 0:
                balance = True
                logger.info(f"Balance is OK")

    def send_launch(self) -> None:
        logger.info(f"Check topic")
        interface = RI.RobonomicsInterface(seed=self.plug_seed)
        if "twin_id" in self.config:
            twin_id = self.config["twin_id"]
        else:
            twins_num = interface.custom_chainstate("DigitalTwin", "Total")
            for i in range(twins_num.value):
                owner = interface.custom_chainstate("DigitalTwin", "Owner", int(i))
                logger.info(f"Owner: {owner}")
                if owner.value == self.service_address:
                    twin_id = i
                    break
        topics = interface.custom_chainstate("DigitalTwin", "DigitalTwin", twin_id)
        plug_address = Keypair.create_from_mnemonic(self.plug_seed, ss58_format=32).ss58_address
        if topics.value is None:
            topics_list = []
        else:
            topics_list = topics.value
        for topic in topics_list:
            if topic[1] == plug_address:
                logger.info(f"Topic exists")
                break
        else:
            logger.info(f"Sending launch to add topic")
            hash = interface.send_launch(self.service_address, True)
            logger.info(f"Launch created with hash {hash}")

    def send_datalog(self, data: dict) -> None:
        logger.info(f"Sending datalog with data {data}")
        interface = RI.RobonomicsInterface(seed=self.plug_seed)
        hash = interface.record_datalog(str(data))
        logger.info(f"Datalog created with hash {hash}")

    def on_message(self, client: mqtt.Client, userdata: None, message: mqtt.MQTTMessage) -> None:
        data = str(message.payload.decode())
        data = json.loads(data)
        if "power" in data:
            energy = self.write_usage(data["power"])
        else:
            energy = self.write_usage(0)
        logger.info(f"Got mqtt message {data}")
        if (time.time() - self.prev_time_sending) > self.config['sending_timeout']:
            self.prev_time_sending = time.time()
            text = {"geo": self.location, "power_usage": energy, "timestamp": time.time()}
            threading.Thread(target=self.send_datalog, name="DatalogSender", args=[text]).start()
            #self.send_datalog(str(text))

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
        with open(f"{self.path}data/configuration.yaml", "r") as config_file:
            config = yaml.safe_load(config_file)
        topics = []
        for device in config["devices"]:
            topic = config["devices"][device]["friendly_name"]
            topic = f"zigbee2mqtt/{topic}"
            topics.append((topic, 1))
        logger.info(f"Topics to subscribe {topics}")
        return topics

    def read_config(self, path: str):
        with open(path) as f:
            config_file = yaml.safe_load(f)
        if "device_seed" not in config_file:
            mnemonic = Keypair.generate_mnemonic()
            logger.info(f"Generated account with address: {Keypair.create_from_mnemonic(mnemonic, ss58_format=32).ss58_address}")
            config_file["device_seed"] = mnemonic
            with open(path, "w") as f:
                yaml.dump(config_file, f)
        else:
            logger.info(f"Your device address is {Keypair.create_from_mnemonic(config_file['device_seed'], ss58_format=32).ss58_address}")
        if "location" not in config_file:
            try:
                config_file["location"] = os.environ["LOCATION"]
            except:
                config_file["location"] = ''
            with open(path, "w") as f:
                yaml.dump(config_file, f)
        return config_file
    
    def spin(self) -> None:
        self.client.loop_forever()
        logger.info("End")

if __name__ == '__main__':
    PlugMonitoring().spin()

