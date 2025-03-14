#!/usr/bin/env python3
import json, logging, os, time, requests, pytz
from datetime import datetime, timedelta

TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"
TIBBER_API_TOKEN = "BxfErG_8Ps08ymt3hOkrZmIkNjSj92VCT638Q5DVo24"
CACHE_FILE = "/root/master_kees/Dynamic_Prices/prices_tibber.json"
LOG_FILE = "/root/master_kees/Dynamic_Prices/logs/tibber_fetcher.log"
CET = pytz.timezone("Europe/Amsterdam")
QUERY = "{viewer{homes{currentSubscription{priceInfo{today{total startsAt}tomorrow{total startsAt}}}}}}"

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger()

def get_cet_now():
    return datetime.now(CET)

def fetch_tibber_prices():
    try:
        headers = {"Authorization": f"Bearer {TIBBER_API_TOKEN}", "Content-Type": "application/json"}
        response = requests.post(TIBBER_API_URL, json={"query": QUERY}, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                return None
            today = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"]
            tomorrow = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["tomorrow"] or []
            prices = {item["startsAt"][:16]: round(item["total"], 3) for item in today + tomorrow}
            logger.info(f"Fetched {len(prices)} hours")
            return prices
        logger.error(f"HTTP {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Fetch failed: {str(e)}")
        return None

def update_cache(prices):
    if prices:
        data = {"retrieved": get_cet_now().isoformat(), "prices": prices}
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Cache updated: {len(prices)} hours")

def main():
    logger.info("Tibber fetcher started")
    # Initial fetch on start/restart
    prices = fetch_tibber_prices()
    if prices:
        update_cache(prices)
    while True:
        try:
            now = get_cet_now()
            next_update = now.replace(hour=13, minute=0, second=0, microsecond=0)
            if now > next_update:
                next_update += timedelta(days=1)
            wait = (next_update - now).total_seconds()
            logger.info(f"Waiting {wait/3600:.1f}h ’til {next_update}")
            time.sleep(wait)

            while get_cet_now().hour < 15:  # Retry ’til 15:00 CET
                prices = fetch_tibber_prices()
                if prices:
                    update_cache(prices)
                    tomorrow = (now + timedelta(days=1)).date().isoformat()
                    if any(ts.startswith(tomorrow) for ts in prices):
                        logger.info("Tomorrow’s prices fetched")
                        break
                logger.info("Retrying in 5m")
                time.sleep(300)
        except Exception as e:
            logger.error(f"Crash: {str(e)}—restarting in 10s")
            time.sleep(10)

if __name__ == "__main__":
    main()