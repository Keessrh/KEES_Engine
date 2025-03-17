#!/usr/bin/env python3
import json, logging, os, signal, time
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
    """Load price data from JSON file, return full dataset."""
    try:
        with open(filename) as f:
            return json.load(f)["prices"]
    except Exception as e:
        logging.error(f"Failed to load {filename}: {e}")
        return {}

def load_fallback_prices():
    """Load previous fused prices in case of failure."""
    try:
        with open(OUTPUT_FILE) as f:
            data = json.load(f)
            prices = data["prices"]
            logging.info(f"Loaded {len(prices)} fallback prices from {data['retrieved']}")
            return prices
    except Exception as e:
        logging.error(f"Fallback failed: {e}")
        return {}

def fuse_prices():
    """Fuse prices from all available data without filtering by a time window."""
    tibber = load_json(TIBBER_FILE)
    entsoe = load_json(ENTSOE_FILE)
    
    # Combine ALL available prices, no filtering
    prices = {**entsoe, **tibber}
    
    if len(prices) >= 1:
        min_price = min(prices.values())
        max_price = max(prices.values())

        if max_price == min_price:
            max_price += 0.001  # Prevent divide by zero error

        percent = {h: ((p - min_price) / (max_price - min_price)) * 100 for h, p in prices.items()}
        logging.info(f"Scaling range: Min={min_price}, Max={max_price}, Total Entries: {len(prices)}")
    else:
        logging.warning(f"No valid prices found, using fallback")
        percent = load_fallback_prices()
        if not percent:
            logging.warning("Fallback empty, defaulting to 50%")
            percent = {now_cet().isoformat(): 50}

    with open(OUTPUT_FILE, "w") as f:
        json.dump({"retrieved": now_cet().isoformat(), "prices": percent}, f)

    logging.info(f"Fused {len(percent)} price entries")

def main():
    logging.info("Price fuser initialized")
    
    # Run IMMEDIATELY—no waiting
    fuse_prices()
    
    while True:
        time.sleep(3600)  # Run every hour
        fuse_prices()

if __name__ == "__main__":
    main()
