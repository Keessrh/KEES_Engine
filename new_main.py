import json
import logging
import os
import threading
from datetime import datetime
import paho.mqtt.client as mqtt
from flask import Flask, jsonify
from zoneinfo import ZoneInfo  # For CET timezone

app = Flask(__name__)
CET = ZoneInfo("Europe/Amsterdam")  # Proper CET timezone
logging.basicConfig(filename="/root/master_kees/new_main.log", level=logging.INFO)
logger = logging.getLogger(__name__)

MQTT_BROKER = "159.223.10.31"
MQTT_PORT = 1884
client = mqtt.Client()
client.on_message = lambda c, u, m: process_data(m.topic, m.payload.decode())
logger.info("Attempting MQTT connection...")
client.connect(MQTT_BROKER, MQTT_PORT)
client.subscribe("julianalaan_39/telemetry")
client.subscribe("julianalaan_39/command")
logger.info("Connected to MQTT broker in new_main.py")
client.loop_start()

from clients.julianalaan_39.heatpump_fixed_fixed import run_heatpump, process_data, get_data

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
    heatpump_data = get_data