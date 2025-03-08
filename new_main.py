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
import collections
from dateutil import tz
import os

app = Flask(__name__)
logging.basicConfig(filename="/root/new_main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

client = mqtt.Client()
MQTT_BROKER = "159.223.10.31"
MQTT_PORT = 1883
client.connect(MQTT_BROKER, MQTT_PORT)
logger.info("Connected to MQTT broker in new_main.py")

huizen = {}
cop_buffer = collections.deque(maxlen=1440)
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
    global cop_buffer
    while True:
        now = datetime.now(CET)
        for huis_id in huizen:
            for device_name in huizen[huis_id]:
                huis_data = huizen[huis_id][device_name]
                while cop_buffer and (now - cop_buffer[0][0]) > timedelta(hours=24):
                    cop_buffer.popleft()
                if cop_buffer:
                    valid_cops = [cop for timestamp, cop in cop_buffer if cop > 0]
                    huis_data["cop_24h"] = sum(valid_cops) / len(valid_cops) if valid_cops else 0.0
                else:
                    huis_data["cop_24h"] = 0.0
        time.sleep(60)

@app.route("/")
def index():
    now = datetime.now(CET)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    if not os.path.exists("/root/master_kees/prices_test.json"):
        with open("/root/master_kees/prices_test.json", "w") as f:
            json.dump({}, f)
    with open("/root/master_kees/prices_test.json", "r") as f:
        price_data = json.load(f) if os.path.getsize("/root/master_kees/prices_test.json") > 0 else {}
    tibber_prices = price_data.get("tibber", {}).get("prices", {})
    entsoe_prices = price_data.get("entsoe", {}).get("prices", {})
    tibber_price = tibber_prices.get(current_hour_str, 0.05)
    entsoe_price = entsoe_prices.get(current_hour_str, 0.05)
    prev_hour = current_hour - timedelta(hours=1)
    next_hour = current_hour + timedelta(hours=1)
    prev_hour_str = prev_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    next_hour_str = next_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    tibber_prev = tibber_prices.get(prev_hour_str, 0.05)
    tibber_next = tibber_prices.get(next_hour_str, 0.05)
    entsoe_prev = entsoe_prices.get(prev_hour_str, 0.05)
    entsoe_next = entsoe_prices.get(next_hour_str, 0.05)
    prev_time = prev_hour.strftime("%a %H:%M")
    current_time = current_hour.strftime("%a %H:%M")
    next_time = next_hour.strftime("%a %H:%M")
    html = """
    <h1>K.E.E.S. Control</h1>
    <div id="dashboard"></div>
    <script>
        function updateDashboard() {
            fetch('/data')
                .then(response => response.json())
                .then(data => {
                    let html = '';
                    for (let huis_id in data.huis_data) {
                        for (let device_name in data.huis_data[huis_id]) {
                            let huis = data.huis_data[huis_id][device_name];
                            let state = huis.energy_state_input_holding || 8;
                            let opwek = huis.opwek || 0;
                            let price = huis.price || 0.05;
                            let entsoe_price = huis.entsoe_price || 0.05;
                            let temp_in = huis.water_inlet_temp || 0;
                            let temp_out = huis.water_outlet_temp || 0;
                            let flow = huis.current_flow_rate || 0;
                            let outdoor_temp = huis.outdoor_air_temp || 0;
                            let power = huis.sdm120_watt || 0;
                            let cop = huis.cop || 0;
                            let cop_24h = huis.cop_24h || 0;
                            let compressor = huis.compressor_status || 0;
                            let dhw = huis.dhw_heating_status || 0;
                            let dhw_target = huis.dhw_target_temp || 0;
                            let target_temp = huis.target_temp_circuit1 || 0;
                            let overschot = opwek - power;
                            let savings = ((0.25 - price) * (power / 1000)).toFixed(2);
                            let decision = "State 8: Normaal verbruik";
                            if (price <= 0.15 || opwek > 2500) decision = "State 5: Laag tarief of overschot > 2500W";
                            else if (price <= 0.25 || opwek > 1500) decision = "State 4: Matig tarief of overschot > 1500W";
                            else if (price <= 0.35) decision = "State 3: Normaal tarief";
                            else decision