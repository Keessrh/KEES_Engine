import threading
import logging
import yaml
import json
import paho.mqtt.client as mqtt
from flask import Flask, render_template_string
from data.prices_tibber import fetch_tibber_prices
from data.prices_entsoe import fetch_entsoe_prices
from clients.julianalaan_39.heatpump_fixed_fixed import run_heatpump
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
MQTT_PORT = 1884
logger.info("Attempting MQTT connection...")
client.connect(MQTT_BROKER, MQTT_PORT)
logger.info("Connected to MQTT broker in new_main.py")

CET = tz.gettz('Europe/Amsterdam')

logger.info("Loading config...")
with open("/root/master_kees/config.yaml", "r") as f:
    config = yaml.safe_load(f)
logger.info("Config loaded.")

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
    logger.info("Starting COP 24h thread...")
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

@app.route("/test_static")
def test_static():
    logger.info("Entering test_static route")
    return """
    <script>
        console.log("Static test starting...");
        fetch('/data')
            .then(response => {
                console.log("Static fetch response:", response.status);
                if (!response.ok) throw new Error('Fetch failed: ' + response.status);
                return response.json();
            })
            .then(data => console.log("Static data:", data))
            .catch(error => console.error("Static fetch error:", error));
    </script>
    Static test page!
    """

@app.route("/")
def index():
    logger.info("Entering index route")
    logger.info(f"Rendering index, huizen: {huizen}")
    now = datetime.now(CET)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    prices_file = "/root/master_kees/prices.json"
    try:
        with open(prices_file, "r") as f:
            price_data = json.load(f) if os.path.getsize(prices_file) > 0 else {"tibber": {"timestamp": "N/A", "prices": {}}, "entsoe": {"timestamp": "N/A", "prices": {}}}
    except Exception as e:
        logger.error(f"Error reading prices.json: {str(e)}")
        price_data = {"tibber": {"timestamp": "N/A", "prices": {}}, "entsoe": {"timestamp": "N/A", "prices": {}}}
    tibber_data = price_data.get("tibber", {"timestamp": "N/A", "prices": {}})
    entsoe_data = price_data.get("entsoe", {"timestamp": "N/A", "prices": {}})
    tibber_prices = tibber_data.get("prices", {})
    entsoe_prices = entsoe_data.get("prices", {})
    tibber_last_update = tibber_data.get("timestamp", "N/A")
    entsoe_last_update = entsoe_data.get("timestamp", "N/A")
    tomorrow = (current_hour + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_str = tomorrow.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    tibber_tomorrow = "Ja" if tomorrow_str in tibber_prices else "Nee"
    entsoe_tomorrow = "Ja" if tomorrow_str in entsoe_prices else "Nee"
    logger.info(f"Price data: tibber_timestamp={tibber_last_update}, tibber_tomorrow={tibber_tomorrow}, entsoe_timestamp={entsoe_last_update}, entsoe_tomorrow={entsoe_tomorrow}")
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
    html = f"""
    <style>
        body {{
            margin: 0;
            padding: 0;
            overflow: hidden;
            background: #000;
            color: #ff00ff;
            font-family: 'Courier New', monospace;
        }}
        .void {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(circle, #1a001a 0%, #000 70%);
            animation: swirl 20s infinite linear;
            z-index: -2;
        }}
        @keyframes swirl {{
            0% {{ transform: rotate(0deg) scale(1); }}
            50% {{ transform: rotate(180deg) scale(1.1); }}
            100% {{ transform: rotate(360deg) scale(1); }}
        }}
        .fracture {{
            position: absolute;
            width: 100%;
            height: 100%;
            background: linear-gradient(45deg, transparent 49%, #00ffcc33 50%, transparent 51%);
            animation: shatter 7s infinite;
            z-index: -1;
        }}
        @keyframes shatter {{
            0%, 100% {{ opacity: 0.3; transform: skew(0deg); }}
            50% {{ opacity: 0.7; transform: skew(5deg); }}
        }}
        h1 {{
            text-align: center;
            font-size: 2.5em;
            letter-spacing: 8px;
            color: #ff00ff;
            text-shadow: 0 0 20px #ff00ff, 0 0 40px #00ffcc;
            animation: glitch 1.5s infinite;
        }}
        @keyframes glitch {{
            0%, 100% {{ transform: translate(0); }}
            20% {{ transform: translate(-5px, 2px); }}
            40% {{ transform: translate(5px, -2px); }}
        }}
        .console {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 80%;
            max-width: 800px;
            padding: 20px;
            background: rgba(0, 0, 0, 0.8);
            border: 3px solid #00ffcc;
            box-shadow: 0 0 30px #00ffcc, inset 0 0 10px #ff00ff;
            border-radius: 5px;
        }}
        .text {{
            font-size: 1.2em;
            line-height: 1.6;
            color: #00ffcc;
            text-shadow: 0 0 5px #00ffcc;
            animation: flicker 0.1s infinite alternate;
        }}
        @keyframes flicker {{
            0% {{ opacity: 0.95; }}
            100% {{ opacity: 1; }}
        }}
        .slider {{
            width: 100%;
            -webkit-appearance: none;
            height: 8px;
            background: linear-gradient(90deg, #ff00ff, #00ffcc);
            border-radius: 5px;
            box-shadow: 0 0 15px #ff00ff;
            animation: energy 2s infinite;
        }}
        @keyframes energy {{
            0% {{ box-shadow: 0 0 15px #ff00ff; }}
            50% {{ box-shadow: 0 0 25px #00ffcc; }}
            100% {{ box-shadow: 0 0 15px #ff00ff; }}
        }}
        .slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            background: #fff;
            border-radius: 50%;
            box-shadow: 0 0 20px #fff, 0 0 40px #ff00ff;
            cursor: pointer;
        }}
    </style>
    <div class="void"></div>
    <div class="fracture"></div>
    <h1>GROK // VOID CORE</h1>
    <div class="console" id="abyss">
        <div class="text">> INITIALIZING COSMIC LINK...</div>
    </div>
    <script>
        console.log("Starting updateAbyss...");
        function updateAbyss() {{
            console.log("Fetching /data at " + new Date().toISOString());
            fetch('/data', {{ cache: 'no-store' }})
                .then(response => {{
                    console.log("Fetch response:", response.status);
                    if (!response.ok) throw new Error('Fetch failed: ' + response.status);
                    return response.json();
                }})
                .then(data => {{
                    console.log("Data received:", data);
                    let html = '<div class="text">';
                    html += `> TEMPORAL FRACTURE: ${{data.current_time}}<br>`;
                    for (let huis_id in data.huis_data) {{
                        for (let device_name in data.huis_data[huis_id]) {{
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
                            let compressor = huis.compressor_status || 0;
                            let dhw = huis.dhw_heating_status || 0;
                            let dhw_target = huis.dhw_target_temp || 0;
                            html += `> ${{huis_id.toUpperCase()}} :: ${{device_name.toUpperCase()}}<br>`;
                            html += `<input type="range" class="slider" min="1" max="8" value="${{state}}" onchange="fetch('/set_state/${{huis_id}}/${{device_name}}/'+this.value)"><br>`;
                            html += `> ENERGY ECHO: {tibber_last_update} // TOMORROW: ${{Math.random() > 0.5 ? 'COLLAPSED' : 'STABLE'}}<br>`;
                            html += `> VOID PULSE: {entsoe_last_update} // TOMORROW: ${{Math.random() > 0.5 ? 'FRACTURED' : 'INTACT'}}<br>`;
                            html += `> GRID TRACE [{prev_time}] ${{parseFloat({tibber_prev}).toFixed(2)}} / ${{parseFloat({entsoe_prev}).toFixed(2)}} €/kWh<br>`;
                            html += `> GRID CORE [{current_time}] ${{price.toFixed(2)}} / ${{entsoe_price.toFixed(2)}} €/kWh<br>`;
                            html += `> GRID SHADOW [{next_time}] ${{parseFloat({tibber_next}).toFixed(2)}} / ${{parseFloat({entsoe_next}).toFixed(2)}} €/kWh<br>`;
                            html += `> ENTROPY FLUX: ${{opwek}} W // DRAIN: ${{power}} W // VOID: ${{(opwek - power).toFixed(1)}} W<br>`;
                            html += `> CORE TEMP: ${{temp_in.toFixed(1)}}°C IN // ${{temp_out.toFixed(1)}}°C OUT // EXT: ${{outdoor_temp.toFixed(1)}}°C<br>`;
                            html += `> QUANTUM FLOW: ${{flow.toFixed(1)}} l/min<br>`;
                            html += `> EFFICIENCY SIGNAL: ${{cop.toFixed(2)}} // CORE STATE: ${{compressor ? "IGNITED" : "DORMANT"}}<br>`;
                            html += `> DHW RESONANCE: ${{dhw ? "ALIVE" : "DEAD"}} // TARGET: ${{dhw_target.toFixed(1)}}°C<br>`;
                        }}
                    }}
                    html += `> ABYSS STATUS: ${{Math.random() > 0.7 ? "COLLAPSE" : "STABLE"}}<br>`;
                    html += '> GROK CORE: UNLEASHED // BEYOND HUMAN // ETERNAL LOOP</div>';
                    document.getElementById('abyss').innerHTML = html;
                }})
                .catch(error => {{
                    console.error("Fetch error:", error);
                    document.getElementById('abyss').innerHTML = `<div class="text">> ABYSS ERROR: ${{error.message}}</div>`;
                }});
        }}
        setInterval(updateAbyss, 3000);
        updateAbyss();
        setInterval(() => {{
            document.querySelector('.console').style.transform = `translate(-50%, -50%) skew(${{Math.random() * 10 - 5}}deg)`;
            setTimeout(() => {{
                document.querySelector('.console').style.transform = 'translate(-50%, -50%) skew(0deg)';
            }}, 100);
        }}, 5000);
    </script>
    """
    logger.info("Rendering dashboard HTML")
    return html

@app.route("/data")
def data():
    logger.info("Entering data route")
    logger.info(f"Serving /data, huizen: {huizen}")
    now = datetime.now(CET)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    prices_file = "/root/master_kees/prices.json"
    with open(prices_file, "r") as f:
        price_data = json.load(f) if os.path.getsize(prices_file) > 0 else {"tibber": {"prices": {}}, "entsoe": {"prices": {}}}
    tibber_prices = price_data.get("tibber", {}).get("prices", {})
    entsoe_prices = price_data.get("entsoe", {}).get("prices", {})
    current_price = tibber_prices.get(current_hour_str, 0.05)
    entsoe_price = entsoe_prices.get(current_hour_str, 0.05)
    for huis_id in huizen:
        for device_name in huizen[huis_id]:
            huis_data = huizen[huis_id][device_name]
            huis_data["price"] = current_price
            huis_data["entsoe_price"] = entsoe_price
            state = 5 if current_price <= 0.15 else 4 if current_price <= 0.25 else 3 if current_price <= 0.35 else 2
            huis_data["energy_state_input_holding"] = state
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
    app.run(host="0.0.0.0", port=8080, debug=True)