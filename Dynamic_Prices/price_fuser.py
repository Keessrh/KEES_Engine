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
            return json.load(f)["prices"]
    except:
        return {}

def wait_for_full_fetch():
    deadline = now_cet().replace(hour=17, minute=0)
    while now_cet() < deadline and not os.path.exists("/tmp/full_fetch_done"):
        logging.info("Waiting for full fetch flag...")
        time.sleep(300)
    if not os.path.exists("/tmp/full_fetch_done"):
        logging.warning("No full fetch by 17:00—using fallback prices")

def fuse_prices():
    tibber = load_json(TIBBER_FILE)
    entsoe = load_json(ENTSOE_FILE)
    prices = entsoe.copy()
    prices.update(tibber)
    now = now_cet()
    last_13 = now.replace(hour=13, minute=0, second=0)
    if now < last_13:
        last_13 -= timedelta(days=1)
    start = last_13
    end = start + timedelta(hours=47)
    start_str = start.strftime("%Y-%m-%dT%H:00")
    end_str = end.strftime("%Y-%m-%dT%H:00")
    prices_filtered = {h: v for h, v in prices.items() if start_str <= h <= end_str}
    
    if not prices_filtered or len(prices_filtered) < 48:
        logging.warning("Incomplete prices, using fallback")
        percent = load_fallback_prices()
        if len(percent) < 48:
            percent = {f"{start + timedelta(hours=i):%Y-%m-%dT%H:00}": 50 for i in range(48)}
    else:
        min_price = min(prices_filtered.values())
        max_price = max(prices_filtered.values())
        if max_price == min_price:
            max_price += 0.001
        percent = {h: ((p - min_price) / (max_price - min_price)) * 100 if max_price != min_price else 50 for h, p in prices_filtered.items()}
        logging.info(f"Scaling range: Min={min_price}, Max={max_price}, Window: {start_str} to {end_str}")
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump({"retrieved": now_cet().isoformat(), "prices": percent}, f)
    logging.info(f"Fused {len(percent)} hours: {start_str} to {end_str}")

def main():
    logging.info("Price fuser initialized")
    now = now_cet()
    if now.hour < 13:
        logging.info("Pre-13:00: fusing with available data")
        fuse_prices()
    else:
        wait_for_full_fetch()
        fuse_prices()
        if os.path.exists("/tmp/full_fetch_done"):
            os.remove("/tmp/full_fetch_done")
    while True:
        now = now_cet()
        next_fuse = now.replace(hour=17, minute=15, second=0)
        if now >= next_fuse:
            next_fuse += timedelta(days=1)
        wait = max(0, (next_fuse - now).total_seconds())
        if wait:
            logging.info(f"Waiting {wait/3600:.1f}h til {next_fuse}")
            time.sleep(wait)
        wait_for_full_fetch()
        fuse_prices()
        if os.path.exists("/tmp/full_fetch_done"):
            os.remove("/tmp/full_fetch_done")

if __name__ == "__main__":
    main()