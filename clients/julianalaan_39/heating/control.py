#!/usr/bin/env python3
# /root/master_kees/clients/julianalaan_39/heating/control.py
import json
import time
from datetime import datetime
import os
import yaml

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def get_price_percent(price_file):
    with open(price_file, "r") as f:
        data = json.load(f)
    return data.get("price_percent", 0)  # Default to 0 if key missing

def decide_heating(price):
    if price == 0:
        return "ES5"
    elif 1 <= price <= 20:
        return "ES6"
    elif 20 < price <= 40:
        return "ES3"
    elif 40 < price <= 60:
        return "ES2"
    elif 60 < price <= 80:
        return "ES7"
    elif 80 < price <= 99:
        return "ES8"
    elif price == 100:
        return "ES1"
    return "UNKNOWN"  # Fallback for unexpected values

def log_decision(log_path, price, decision):
    today = datetime.now().strftime("%Y-%m-%d")
    csv_file = os.path.join(log_path, f"{today}.csv")
    header = "timestamp,price_percent,decision\n"
    line = f"{datetime.now().isoformat()},{price},{decision}\n"
    if not os.path.exists(csv_file):
        with open(csv_file, "w") as f:
            f.write(header)
    with open(csv_file, "a") as f:
        f.write(line)

def main():
    config = load_config()
    while True:
        price = get_price_percent(config["price_file"])
        decision = decide_heating(price)
        log_decision(config["log_path"], price, decision)
        time.sleep(config["interval"])

if __name__ == "__main__":
    main()