#!/usr/bin/env python3
import json
import time
from datetime import datetime, timedelta
import os
import yaml
import sys
import paho.mqtt.client as mqtt
import logging

LOG_FILE = "/root/master_kees/logs/dhw.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    force=True
)
logger = logging.getLogger("dhw")

def load_config():
    try:
        with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config.yaml: {e}")
        sys.exit(1)

def get_price_percent(price_file):
    try:
        with open(price_file, "r") as f:
            data = json.load(f)
        now = datetime.now().strftime("%Y-%m-%dT%H:00")
        return data["prices"].get(now, 0)
    except Exception as e:
        logger.error(f"Error reading {price_file}: {e}")
        return 0

def decide_dhw(price):
    return "ON" if price <= 60 else "OFF"

def log_decision(log_path, price, decision, solar, tank_temp):
    try:
        abs_log_path = os.path.join(BASE_DIR, log_path)
        os.makedirs(abs_log_path, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        csv_file = os.path.join(abs_log_path, f"{today}.csv")
        header = "timestamp,price_percent,solar,tank_temp,decision\n"
        line = f"{datetime.now().isoformat()},{price},{solar},{tank_temp},{decision}\n"
        if not os.path.exists(csv_file):
            with open(csv_file, "w") as f:
                f.write(header)
        with open(csv_file, "a") as f:
            f.write(line)
    except Exception as e:
        logger.error(f"Error logging to {csv_file}: {e}")

def on_connect(client, userdata, flags, rc):
    logger.info(f"Connected to MQTT broker with code {rc}")
    client.subscribe(userdata["topic"])

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    userdata["solar"] = float(payload.get("opwek", 0))
    userdata["tank_temp"] = float(payload.get("dhw_water_temp", 0))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def sleep_to_next_hour():
    now = datetime.now()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=1, microsecond=0)
    sleep_time = (next_hour - now).total_seconds()
    logger.info(f"Sleeping {sleep_time:.0f}s until {next_hour}")
    time.sleep(sleep_time)

def main():
    config = load_config()
    logger.info(f"Starting DHW control with interval {config['interval']}s")
    telemetry = {"solar": 0, "tank_temp": 0, "topic": config["mqtt"]["topic"]}
    client = mqtt.Client(userdata=telemetry)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(config["mqtt"]["broker"], config["mqtt"]["port"])
    client.loop_start()
    sleep_to_next_hour()
    while True:
        price = get_price_percent(config["price_file"])
        decision = decide_dhw(price)
        logger.info(f"Price: {price}, Decision: {decision}, Solar: {telemetry['solar']}, Tank Temp: {telemetry['tank_temp']}")
        log_decision(config["log_path"], price, decision, telemetry["solar"], telemetry["tank_temp"])
        logger.info("Cycle complete, sleeping until next hour")
        sleep_to_next_hour()

if __name__ == "__main__":
    main()