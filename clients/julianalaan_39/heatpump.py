import logging
import time
import paho.mqtt.client as mqtt
from datetime import datetime
from dateutil import tz

logging.basicConfig(filename="/root/new_main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

MQTT_BROKER = "159.223.10.31"
MQTT_PORT = 1883
CET = tz.gettz('Europe/Amsterdam')

def on_message(client, userdata, msg):
    logger.info(f"Received: {msg.topic} - {msg.payload}")

def run_heatpump():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe("julianalaan_39/telemetry")
    client.subscribe("julianalaan_39/command")
    client.loop_start()
    while True:
        now = datetime.now(CET)
        current_hour = now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00.000+01:00")
        with open("/root/master_kees/prices_test.json", "r") as f:
            price_data = json.load(f) if os.path.getsize("/root/master_kees/prices_test.json") > 0 else {}
        tibber_prices = price_data.get("tibber", {}).get("prices", {})
        current_price = tibber_prices.get(current_hour, 0.05)
        state = 5 if current_price <= 0.15 else 4 if current_price <= 0.25 else 3 if current_price <= 0.35 else 2
        client.publish("julianalaan_39/command", json.dumps({"energy_state_input_holding": state}))
        logger.info(f"Heatpump set state {state} for price {current_price} €/kWh")
        time.sleep(5)
