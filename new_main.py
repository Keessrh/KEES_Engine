import threading
import logging
import yaml
import json
import paho.mqtt.client as mqtt
from flask import Flask, render_template_string
from data.prices_tibber import fetch_tibber_prices
from data.prices_entsoe import fetch_entsoe_prices
from clients.julianalaan_39.heatpump import run_heatpump
from datetime import datetime, timedelta
from dateutil import tz
import os
import time
from shared_data import huizen, cop_buffer

app = Flask(__name__)
logging.basicConfig(filename="/root/new_main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

client = mqtt.Client()
MQTT_BROKER = "159.223.10.31"
MQTT_PORT = 1883
client.connect(MQTT_BROKER, MQTT_PORT)
logger.info("Connected to MQTT broker in new_main.py")

CET = tz.gettz('Europe/Amsterdam')

with open("/root/master_kees/config.yaml", "r") as f:
    config = yaml.safe_load(f)

def calculate_cop(power, temp_in, temp_out, flow):
    try:
        power = float(power or 0)
        temp_in = float(temp_in or 0)
        temp_out = float(temp_out or 0)
        flow = float(flow or 0)
        if power <= 0 or flow <= 0 or temp_out <= temp_in:
            return 0.0
        heat_output = (flow * (temp_out - temp_in) * 4.18) / 60
        cop = heat_output / (power / 1000)
        return cop
    except Exception as e:
        logger.error(f"COP calc error: {str(e)}")
        return 0.0

def update_cop_24h():
    while True:
        now = datetime.now(CET)
        for huis_id in huizen:
            for device_name in huizen[huis_id]:
                huis_data = huizen[huis_id][device_name]
                while cop_buffer and (now - cop_buffer[0][0]) > timedelta(hours=24):
                    cop_buffer.pop(0)
                if cop_buffer:
                    valid_cops = [cop for timestamp, cop in cop_buffer if cop > 0]
                    huis_data["cop_24h"] = sum(valid_cops) / len(valid_cops) if valid_cops else 0.0
                else:
                    huis_data["cop_24h"] = 0.0
        time.sleep(60)

@app.route("/test")
def test():
    logger.info("Entering test route")
    return "Test page works!"

@app.route("/")
def index():
    logger.info("Entering index route")
    logger.info(f"Rendering index, huizen: {huizen}")
    return "Hello, K.E.E.S. is alive!"

@app.route("/data")
def data():
    logger.info("Entering data route")
    logger.info(f"Serving /data, huizen: {huizen}")
    now = datetime.now(CET)
    data_to_return = {"huis_data": huizen, "current_time": now.strftime("%a, %d %b %Y %H:%M:%S CET")}
    logger.info(f"Returning data: {json.dumps(data_to_return)}")
    return json.dumps(data_to_return)

@app.route("/set_state/<huis_id>/<device_name>/<int:state>")
def set_state(huis_id, device_name, state):
    logger.info(f"Entering set_state route for {huis_id}/{device_name} with state {state}")
    client.publish(f"{huis_id}/command", json.dumps({"energy_state_input_holding": state}))
    logger.info(f"State set: {huis_id}/{device_name} to {state}")
    return "State set!"

if __name__ == "__main__":
    logger.info("Starting NEW K.E.E.S. Engine (mirroring main.py)")
    threading.Thread(target=fetch_tibber_prices, daemon=True).start()
    threading.Thread(target=fetch_entsoe_prices, daemon=True).start()
    threading.Thread(target=run_heatpump, daemon=True).start()
    threading.Thread(target=update_cop_24h, daemon=True).start()
    logger.info("New engine running—mirroring main.py with all pieces!")
    logger.info(f"new_main.py huizen at start: {huizen}")
    client.loop_start()
    app.run(host="0.0.0.0", port=8080)