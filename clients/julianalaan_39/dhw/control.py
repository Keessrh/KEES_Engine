#!/usr/bin/env python3
import json
import time
from datetime import datetime
import os
import yaml
import sys

# Get the directory of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_config():
    try:
        with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config.yaml: {e}", file=sys.stderr)
        sys.exit(1)

def get_price_percent(price_file):
    try:
        with open(price_file, "r") as f:
            data = json.load(f)
        # Get current hour's price
        now = datetime.now().strftime("%Y-%m-%dT%H:00")
        return data["prices"].get(now, 0)  # Default to 0 if hour missing
    except Exception as e:
        print(f"Error reading {price_file}: {e}", file=sys.stderr)
        return 0

def decide_dhw(price):
    return "ON" if price <= 60 else "OFF"

def log_decision(log_path, price, decision):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        csv_file = os.path.join(log_path, f"{today}.csv")
        header = "timestamp,price_percent,decision\n"
        line = f"{datetime.now().isoformat()},{price},{decision}\n"
        if not os.path.exists(csv_file):
            with open(csv_file, "w") as f:
                f.write(header)
        with open(csv_file, "a") as f:
            f.write(line)
    except Exception as e:
        print(f"Error logging to {csv_file}: {e}", file=sys.stderr)

def main():
    config = load_config()
    print(f"Starting DHW control with interval {config['interval']}s")
    while True:
        price = get_price_percent(config["price_file"])
        decision = decide_dhw(price)
        log_decision(config["log_path"], price, decision)
        print(f"Price: {price}, Decision: {decision}")
        time.sleep(config["interval"])

if __name__ == "__main__":
    main()