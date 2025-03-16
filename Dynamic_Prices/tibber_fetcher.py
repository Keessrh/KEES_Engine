#!/usr/bin/env python3
import json
import logging
import os
import signal
import time
import requests
from datetime import datetime, timedelta
import pytz

API_URL = "https://api.tibber.com/v1-beta/gql"
TOKEN = "BxfErG_8Ps08ymt3hOkrZmIkNjSj92VCT638Q5DVo24"
CACHE = "/root/master_kees/Dynamic_Prices/prices_tibber.json"
LOG = "/root/master_kees/Dynamic_Prices/logs/tibber_fetcher.log"
CET = pytz.timezone("Europe/Amsterdam")

os.makedirs(os.path.dirname(LOG), exist_ok=True)
logging.basicConfig(filename=LOG, level=logging.INFO, format="%(asctime)s - %(message)s")

def signal_handler(signum, frame):
    logging.info("Shutting down")
    exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def now_cet():
    return datetime.now(CET)

def fetch_tibber():
    try:
        query = """
        {
          viewer {
            homes {
              currentSubscription {
                priceInfo {
                  today { total startsAt }
                  tomorrow { total startsAt }
                }
              }
            }
          }
        }
        """
        r = requests.post(API_URL, json={"query": query}, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}: {r.text}")
        data = r.json()
        if "errors" in data:
            raise Exception(f"GraphQL error: {data['errors']}")
        prices = {p["startsAt"][:16]: round(p["total"], 3) for p in data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"] + (data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["tomorrow"] or [])}
        logging.info(f"Fetched {len(prices)} hours")
        return prices
    except Exception as e:
        logging.error(f"Fetch failed: {e}")
        return {}

def load_cache(filename=CACHE):
    try:
        with open(filename) as f:
            return json.load(f)["prices"]
    except:
        return {}

def save_prices(prices, filename=CACHE):
    current = load_cache(filename)
    current.update(prices)  # Merge new into current
    with open(filename, "w") as f:
        json.dump({"retrieved": now_cet().isoformat(), "prices": current}, f)
    logging.info(f"Saved {len(current)} hours")

def main():
    logging.info("Tibber fetcher initialized")
    prices = fetch_tibber()
    save_prices(prices)
    
    while True:
        now = now_cet()
        next_fetch = now.replace(hour=13, minute=0, second=0)
        if now >= next_fetch:
            next_fetch += timedelta(days=1)
        wait = max(0, (next_fetch - now).total_seconds())
        if wait:
            logging.info(f"Waiting {wait/3600:.1f}h til {next_fetch}")
            time.sleep(wait)
        
        deadline = now_cet().replace(hour=15, minute=0, second=0)
        while now_cet() < deadline:
            prices = fetch_tibber()
            save_prices(prices)
            if len(prices) >= 34:
                break
            logging.info("Incomplete data—retrying in 5m")
            time.sleep(300)
        
        time.sleep(24 * 3600)

if __name__ == "__main__":
    main()