#!/usr/bin/env python3
import json, logging, os, signal, time, requests, pytz
from datetime import datetime, timedelta

API_URL = "https://api.tibber.com/v1-beta/gql"
TOKEN = "BxfErG_8Ps08ymt3hOkrZmIkNjSj92VCT638Q5DVo24"
CACHE = "prices_tibber.json"
LOG = "logs/tibber_fetcher.log"
CET = pytz.timezone("Europe/Amsterdam")
QUERY = "{viewer{homes{currentSubscription{priceInfo{today{total startsAt}tomorrow{total startsAt}}}}}}"

os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename=LOG, level=logging.INFO, format="%(asctime)s - %(message)s")

def signal_handler(signum, frame):
    logging.info("Entropy calls—shutting down")
    exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def now_cet():
    return datetime.now(CET)

def fetch():
    try:
        r = requests.post(API_URL, json={"query": QUERY}, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if "errors" in data: raise Exception("GraphQL error")
            prices = {item["startsAt"][:16]: round(item["total"], 3) 
                     for item in data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"] + 
                                 (data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["tomorrow"] or [])}
            logging.info(f"Fetched {len(prices)} hours")
            return prices
        raise Exception(f"HTTP {r.status_code}")
    except Exception as e:
        logging.error(f"Fetch failed: {e}")
        return None

def load():
    if os.path.exists(CACHE):
        with open(CACHE) as f: return json.load(f).get("prices", {})
    return {}

def save(prices):
    with open(CACHE, "w") as f:
        json.dump({"retrieved": now_cet().isoformat(), "prices": prices}, f)
    logging.info(f"Saved {len(prices)} hours")

def main():
    logging.info("Grok’s divine fetcher begins")
    last = load()  # Fixed: no args needed
    while True:
        now = now_cet()
        next_run = now.replace(hour=13, minute=0, second=0)
        if now >= next_run: next_run += timedelta(days=1)
        wait = max(0, (next_run - now).total_seconds())
#        if wait:
            logging.info(f"Waiting {wait/3600:.1f}h ’til {next_run}")
#            time.sleep(wait)

        while now.hour < 15:
            prices = fetch()
            if prices and len(prices) >= 48:
                save(prices)
                last = prices
                break
            logging.info("No full data—retry in 5m")
            time.sleep(300)
            now = now_cet()

        if not prices:
            logging.warning("Using cache")
            save(last)
        time.sleep(max(0, (now.replace(hour=13, minute=0, second=0) + timedelta(days=1) - now_cet()).total_seconds()))

if __name__ == "__main__":
    main()