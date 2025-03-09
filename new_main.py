import json
import logging
import os
import threading
from datetime import datetime
import paho.mqtt.client as mqtt
from flask import Flask, jsonify

app = Flask(__name__)
CET = lambda: datetime.now().astimezone().replace(microsecond=0)  # Simple CET timezone
logging.basicConfig(filename="/root/master_kees/new_main.log", level=logging.INFO)
logger = logging.getLogger(__name__)

MQTT_BROKER = "159.223.10.31"
MQTT_PORT = 1883
client = mqtt.Client()
client.on_message = lambda c, u, m: process_data(m.topic, m.payload.decode())
logger.info("Attempting MQTT connection...")
client.connect(MQTT_BROKER, MQTT_PORT)
client.subscribe("julianalaan_39/telemetry")
client.subscribe("julianalaan_39/command")
logger.info("Connected to MQTT broker in new_main.py")
client.loop_start()

from clients.julianalaan_39.heatpump_fixed import run_heatpump, process_data, get_data

def fetch_tibber_prices():
    # Placeholder—copy from main.py if needed
    pass

def fetch_entsoe_prices():
    # Placeholder—copy from main.py if needed
    pass

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
    </script>
    """

@app.route("/")
def index():
    logger.info("Entering index route")
    return "GROK // VOID CORE - Check /data for heatpump stats"

@app.route("/data")
def data():
    logger.info("Entering data route")
    heatpump_data = get_data()
    logger.info(f"Serving /data, heatpump_data: {heatpump_data}")
    now = datetime.now(CET)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    prices_file = "/root/master_kees/prices.json"
    try:
        with open(prices_file, "r") as f:
            price_data = json.load(f) if os.path.getsize(prices_file) > 0 else {"tibber": {"timestamp": "N/A", "prices": {}}, "entsoe": {"timestamp": "N/A", "prices": {}}}
    except Exception as e:
        logger.error(f"Error reading prices.json: {e}")
        price_data = {"tibber": {"prices": {}}, "entsoe": {"prices": {}}}
    tibber_prices = price_data.get("tibber", {}).get("prices", {})
    entsoe_prices = price_data.get("entsoe", {}).get("prices", {})
    return jsonify({
        "tibber": {"prices": tibber_prices},
        "entsoe": {"prices": entsoe_prices},
        "heatpump": heatpump_data
    })

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
    run_heatpump()  # Initial call
    app.run(host="0.0.0.0", port=8080, debug=True)