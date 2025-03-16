#!/usr/bin/env python3
import json
import logging
import os
import signal
import time
from datetime import datetime, timedelta
import pytz

CET = pytz.timezone("Europe/Amsterdam")
LOG = "/root/master_kees/Dynamic_Prices/logs/price_fuser.log"
TIBBER_FILE = "/root/master_kees/Dynamic_Prices/prices_tibber.json"
ENTSOE_FILE = "/root/master_kees/Dynamic_Prices/prices_entsoe.json"
OUTPUT_FILE = "/root/master_kees/Dynamic_Prices/prices_percent.json"

os.makedirs(os.path.dirname(LOG), exist_ok=True)
logging.basicConfig(filename=LOG, level=logging.INFO, format="%(asctime)s - %(message)s")

def signal_handler(signum, frame):
    logging.info("Shutting down")
    exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def now_cet():
    return datetime.now(CET)

def load_json(filename):
    try:
        with open(filename) as f:
            return json.load(f)["prices"]
    except:
        return {}

def fuse_prices():
    try:
        tibber = load_json(TIBBER_FILE)
        entsoe = load_json(ENTSOE_FILE)
        
        # Merge all data, Tibber overrides ENTSO-E
        prices = entsoe.copy()
        prices.update(tibber)
        
        now = now_cet()
        last_13 = now.replace(hour=13, minute=0, second=0)
        if now < last_13:
            last_13 -= timedelta(days=1)
        start = last_13
        end = start.replace(hour=23, minute=0, second=0) + timedelta(days=1)  # 34hr
        start_str = start.strftime("%Y-%m-%dT%H:00")
        end_str = end.strftime("%Y-%m-%dT%H:00")
        
        prices_filtered = {h: v for h, v in prices.items() if start_str <= h <= end_str}
        if len(prices_filtered) < 34:
            logging.warning(f"Only {len(prices_filtered)} hours—using all available")
        
        min_price, max_price = 0.206, 0.302
        percent = {}
        for h, p in prices_filtered.items():
            if p <= min_price:
                percent[h] = 0.0
            elif p >= max_price:
                percent[h] = 100.0
            else:
                percent[h] = ((p - min_price) / (max_price - min_price)) * 100
        
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"retrieved": now_cet().isoformat(), "prices": percent}, f)
        logging.info(f"Fused {len(percent)} hours: {start_str} to {end_str}")
    except Exception as e:
        logging.error(f"Fusion failed: {e}")

def main():
    logging.info("Price fuser initialized")
    fuse_prices()
    while True:
        now = now_cet()
        next_fuse = now.replace(hour=13, minute=15, second=0)
        if now >= next_fuse:
            next_fuse += timedelta(days=1)
        wait = max(0, (next_fuse - now).total_seconds())
        if wait:
            logging.info(f"Waiting {wait/3600:.1f}h til {next_fuse}")
            time.sleep(wait)
        
        fuse_prices()
        time.sleep(24 * 3600)

if __name__ == "__main__":
    main()