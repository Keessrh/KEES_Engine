import threading
import logging
import yaml
import json
import paho.mqtt.client as mqtt
from data.prices_tibber import fetch_tibber_prices
from data.prices_entsoe import fetch_entsoe_prices
from clients.julianalaan_39.heatpump import run_heatpump

logging.basicConfig(filename="/root/new_main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

client = mqtt.Client()
MQTT_BROKER = "159.223.10.31"
MQTT_PORT = 1883
client.connect(MQTT_BROKER, MQTT_PORT)
logger.info("Connected to MQTT broker in new_main.py")

with open("/root/master_kees/config.yaml", "r") as f:
    config = yaml.safe_load(f)

if __name__ == "__main__":
    logger.info("Starting NEW K.E.E.S. Engine (test mode)")
    threading.Thread(target=fetch_tibber_prices, daemon=True).start()
    threading.Thread(target=fetch_entsoe_prices, daemon=True).start()
    threading.Thread(target=run_heatpump, daemon=True).start()
    logger.info("New engine running—mirroring main.py with Tibber, ENTSO-E, and heatpump!")
    client.loop_start()
    while True:
        pass
