import logging
import time
import paho.mqtt.client as mqtt
from datetime import datetime
from dateutil import tz
import json
import os

logging.basicConfig(filename="/root/new_main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

MQTT_BROKER = "159.223.10.31"
MQTT_PORT = 1883
CET = tz.gettz('Europe/Amsterdam')
huizen = {"julianalaan_39": {"warmtepomp": {}}}
cop_buffer = []

def on_message(client, userdata, msg):
    global cop_buffer
    logger.info(f"Received: {msg.topic} - {msg.payload}")
    parts = msg.topic.split("/")
    if len(parts) >= 2 and parts[0] == "julianalaan_39":
        if parts[1] == "telemetry":
            payload = json.loads(msg.payload.decode())
            huis_data = huizen["julianalaan_39"]["warmtepomp"]
            for key in payload:
                huis_data[key] = float(payload.get(key, huis_data.get(key, 0)))
            if huis_data.get("compressor_status") == 1:
                cop = calculate_cop(
                    huis_data.get("sdm120_watt", 0),
                    huis_data.get("water_inlet_temp", 0),
                    huis_data.get("water_outlet_temp", 0),
                    huis_data.get("current_flow_rate", 0)
                )
                huis_data["cop"] = cop
                if cop > 0:
                    cop_buffer.append((datetime.now(CET), cop))
            else:
                huis_data["cop"] = 0.0
            huizen["julianalaan_39"]["warmtepomp"] = huis_data
            logger.info(f"Updated huizen: {huizen}")  # Debug to confirm

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

def run_heatpump():
    prices_file = "/root/master_kees/prices_test.json"
    if not os.path.exists(prices_file):
        with open(prices_file, "w") as f:
            json.dump({}, f)
            logger.info(f"Created {prices_file}")
    
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe("julianalaan_39/telemetry")
    client.subscribe("julianalaan_39/command")
    client.loop_start()
    logger.info("Heatpump thread started, MQTT loop running")
    
    while True:
        now = datetime.now(CET)
        current_hour = now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00.000+01:00")
        try:
            with open(prices_file, "r") as f:
                price_data = json.load(f) if os.path.getsize(prices_file) > 0 else {}
        except Exception as e:
            logger.error(f"Price file read error: {str(e)}")
            price_data = {}
        tibber_prices = price_data.get("tibber", {}).get("prices", {})
        current_price = tibber_prices.get(current_hour, 0.05)
        state = 5 if current_price <= 0.15 else 4 if current_price <= 0.25 else 3 if current_price <= 0.35 else 2
        client.publish("julianalaan_39/command", json.dumps({"energy_state_input_holding": state}))
        logger.info(f"Heatpump set state {state} for price {current_price} €/kWh")
        time.sleep(5)