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

@app.route("/")
def index():
    logger.info("Entering index route")
    logger.info(f"Rendering index, huizen: {huizen}")
    now = datetime.now(CET)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    prices_file = "/root/master_kees/prices.json"
    if not os.path.exists(prices_file):
        with open(prices_file, "w") as f:
            json.dump({"tibber": {"last_update": "", "tomorrow_prices_known": False, "prices": {}}, 
                       "entsoe": {"last_update": "", "tomorrow_prices_known": False, "prices": {}}}, f)
    with open(prices_file, "r") as f:
        price_data = json.load(f) if os.path.getsize(prices_file) > 0 else {"tibber": {"prices": {}}, "entsoe": {"prices": {}}}
    tibber_prices = price_data.get("tibber", {}).get("prices", {})
    entsoe_prices = price_data.get("entsoe", {}).get("prices", {})
    tibber_last_update = price_data.get("tibber", {}).get("last_update", "")
    entsoe_last_update = price_data.get("entsoe", {}).get("last_update", "")
    tibber_tomorrow = price_data.get("tibber", {}).get("tomorrow_prices_known", False)
    entsoe_tomorrow = price_data.get("entsoe", {}).get("tomorrow_prices_known", False)
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
    <p><b>Prijs Status:</b></p>
    <p>Tibber - Laatste Update: {{ tibber_last_update }} | Tomorrow Prijzen Bekend: {% if tibber_tomorrow %}Ja{% else %}Nee{% endif %}</p>
    <p>ENTSO-E - Laatste Update: {{ entsoe_last_update }} | Tomorrow Prijzen Bekend: {% if entsoe_tomorrow %}Ja{% else %}Nee{% endif %}</p>
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
                            else decision = "State 2: Hoog tarief";
                            html += `
                                <h3>${huis_id} - ${device_name}</h3>
                                <input type='range' min='1' max='8' value='${state}' onchange='fetch("/set_state/${huis_id}/${device_name}/"+this.value)'>
                                <p><b>Live Waarden:</b></p>
                                <p>Laatste Update: ${data.current_time}</p>
                                <p>Prijs Vorige Uur ({{ prev_time }}): {{ tibber_prev.toFixed(2) }} €/kWh (Tibber) | {{ entsoe_prev.toFixed(2) }} €/kWh (ENTSO-E)</p>
                                <p>Prijs Nu ({{ current_time }}): ${price.toFixed(2)} €/kWh (Tibber) | ${entsoe_price.toFixed(2)} €/kWh (ENTSO-E)</p>
                                <p>Prijs Volgende Uur ({{ next_time }}): {{ tibber_next.toFixed(2) }} €/kWh (Tibber) | {{ entsoe_next.toFixed(2) }} €/kWh (ENTSO-E)</p>
                                <p>Opwek: ${opwek} W | Verbruik: ${power} W | Overschot: ${overschot} W</p>
                                <p>Temp In: ${temp_in.toFixed(1)}°C | Temp Out: ${temp_out.toFixed(1)}°C</p>
                                <p>Stroom (Flow): ${flow.toFixed(1)} l/min | Buitentemp: ${outdoor_temp.toFixed(1)}°C</p>
                                <p>COP: ${cop.toFixed(2)} | COP 24h: ${cop_24h.toFixed(2)} | Compressor: ${compressor ? "Aan" : "Uit"}</p>
                                <p>DHW: ${dhw ? "Aan" : "Uit"} | DHW Doel: ${dhw_target.toFixed(1)}°C</p>
                                <p>Doeltemp Circuit 1: ${target_temp.toFixed(1)}°C</p>
                                <p><b>Besparing:</b> €${savings} per uur (vs 0.25 €/kWh)</p>
                                <p><b>Beslissing:</b> ${decision}</p>
                            `;
                        }
                    }
                    document.getElementById('dashboard').innerHTML = html;
                });
        }
        setInterval(updateDashboard, 5000);
        updateDashboard();
    </script>
    """
    logger.info("Rendering dashboard HTML")
    return render_template_string(html, tibber_last_update=tibber_last_update, entsoe_last_update=entsoe_last_update, 
                                  tibber_tomorrow=tibber_tomorrow, entsoe_tomorrow=entsoe_tomorrow, 
                                  tibber_prev=tibber_prev, tibber_next=tibber_next, 
                                  entsoe_prev=entsoe_prev, entsoe_next=entsoe_next, 
                                  prev_time=prev_time, current_time=current_time, next_time=next_time)

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