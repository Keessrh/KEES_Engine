#!/usr/bin/env python3
import json, logging, os, signal, time, requests, pytz
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

TOKEN = "df3889a7-1758-493e-be53-dac8605fc94c"
API_URL = "https://web-api.tp.entsoe.eu/api"
REGION = "10YNL----------L"
CACHE = "prices_entsoe.json"
LOG = "logs/entsoe_fetcher.log"
CET = pytz.timezone("Europe/Amsterdam")

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
        today = now_cet().date()
        params = {"securityToken": TOKEN, "documentType": "A44", "in_Domain": REGION, "out_Domain": REGION,
                  "periodStart": today.strftime("%Y%m%d") + "0000", "periodEnd": (today + timedelta(days=1)).strftime("%Y%m%d") + "2300"}
        r = requests.get(API_URL, params=params, timeout=10)
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            prices = {}
            for p in root.findall(".//{*}Period"):
                start = datetime.strptime(p.find(".//{*}start").text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=pytz.UTC).astimezone(CET)
                for pt in p.findall(".//{*}Point"):
                    pos = int(pt.find("{*}position").text) - 1
                    prices[start.replace(hour=pos).strftime("%Y-%m-%dT%H:00")] = round(float(pt.find("{*}price.amount").text) / 1000, 3)
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
    last = load()
    prices = fetch()  # Fetch on startup
    if prices:
        save(prices)
        last = prices
    else:
        logging.warning("Startup fetch failed—using cache")
        save(last)
    
    while True:
        now = now_cet()
        next_run = now.replace(hour=13, minute=0, second=0)
        if now >= next_run: next_run += timedelta(days=1)
        wait = max(0, (next_run - now).total_seconds())
        if wait:
            logging.info(f"Waiting {wait/3600:.1f}h ’til {next_run}")
            time.sleep(wait)

        prices = None
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
            prices = last
            save(prices)
        time.sleep(max(0, (now.replace(hour=13, minute=0, second=0) + timedelta(days=1) - now_cet()).total_seconds()))

if __name__ == "__main__":
    main()