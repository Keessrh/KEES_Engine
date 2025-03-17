#!/usr/bin/env python3
import json, logging, os, signal, time, requests
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
    source = "Tibber" if prices else "None"
    if len(prices) >= 48:
        current = prices
        min_price = min(prices.values())
        max_price = max(prices.values())
        logging.info(f"FULL FETCH: {len(prices)} hours, Min={min_price}, Max={max_price}, Source={source}")
    else:
        current.update(prices)
        logging.info(f"Partial fetch: {len(prices)} hours updated, Source={source}")
    with open(filename, "w") as f:
        json.dump({"retrieved": now_cet().isoformat(), "prices": current, "last_fetch": now_cet().isoformat()}, f)
    if len(prices) >= 48:
        open("/tmp/full_fetch_done", "w").close()

def main():
    if os.path.exists("/tmp/full_fetch_done"):
        os.remove("/tmp/full_fetch_done")
    logging.info("Tibber fetcher initialized")
    prices = fetch_tibber()
    if len(prices) < 48 and now_cet().hour < 13:
        logging.info(f"Pre-13:00: only {len(prices)}h fetched—awaiting 13:00 update")
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
        deadline = now_cet().replace(hour=17, minute=0)
        while now_cet() < deadline and len(prices) < 48:
            prices = fetch_tibber()
            save_prices(prices)
            if len(prices) >= 48:
                break
            logging.info("Incomplete—retrying in 5m")
            time.sleep(300)
        time.sleep(24 * 3600)

if __name__ == "__main__":
    main()