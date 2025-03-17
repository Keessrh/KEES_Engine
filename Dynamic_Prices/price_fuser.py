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
    try:
        with open(filename) as f:
            return json.load(f)["prices"]
    except:
        return {}

def load_fallback_prices():
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
    tibber = load_json(TIBBER_FILE)
    entsoe = load_json(ENTSOE_FILE)
    prices = entsoe.copy()
    prices.update(tibber)

    # Use all available prices, no tight filtering
    prices_filtered = prices

    if len(prices_filtered) >= 48:
        min_price = min(prices_filtered.values())
        max_price = max(prices_filtered.values())
        if max_price == min_price:
            max_price += 0.001
        percent = {h: round(((p - min_price) / (max_price - min_price)) * 100, 1) if max_price != min_price else 50 for h, p in prices_filtered.items()}
        logging.info(f"Scaling range: Min={min_price}, Max={max_price}, Window: {len(prices_filtered)} hours")
    else:
        logging.warning(f"Incomplete prices: {len(prices_filtered)} hours, using fallback")
        percent = load_fallback_prices()
        if len(percent) < 48 or not percent:
            logging.warning("Fallback empty or incomplete, defaulting to 50%")
            percent = {f"{now_cet().replace(hour=13, minute=0, second=0) + timedelta(hours=i):%Y-%m-%dT%H:00}": 50 for i in range(48)}
        else:
            logging.info(f"Using {len(percent)} fallback prices")
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump({"retrieved": now_cet().isoformat(), "prices": percent}, f)
    logging.info(f"Fused {len(percent)} hours")

def main():
    logging.info("Price fuser initialized")
    
    # Run ASAP—No Waiting
    fuse_prices()
    
    while True:
        now = now_cet()
        next_fuse = now.replace(hour=17, minute=15, second=0)
        if now >= next_fuse:
            next_fuse += timedelta(days=1)
        wait = max(0, (next_fuse - now).total_seconds())
        logging.info(f"Waiting {wait/3600:.1f}h til {next_fuse}")
        time.sleep(wait)
        fuse_prices()

if __name__ == "__main__":
    main()
