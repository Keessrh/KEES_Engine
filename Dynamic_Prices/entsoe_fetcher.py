#!/usr/bin/env python3
import json, logging, os, signal, time, requests
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
import pytz

TOKEN = "df3889a7-1758-493e-be53-dac8605fc94c"
API_URL = "https://web-api.tp.entsoe.eu/api"
REGION = "10YNL----------L"
CACHE = "/root/master_kees/Dynamic_Prices/prices_entsoe.json"
LOG = "/root/master_kees/Dynamic_Prices/logs/entsoe_fetcher.log"
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

def fetch_entsoe():
    try:
        now = now_cet()
        start = now.replace(hour=0, minute=0, second=0)
        if now.hour < 13:
            start -= timedelta(days=1)
        end = start + timedelta(hours=48)
        params = {
            "securityToken": TOKEN,
            "documentType": "A44",
            "in_Domain": REGION,
            "out_Domain": REGION,
            "periodStart": start.strftime("%Y%m%d%H%M"),
            "periodEnd": end.strftime("%Y%m%d%H%M")
        }
        r = requests.get(API_URL, params=params, timeout=10)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}: {r.text}")
        root = ET.fromstring(r.text)
        prices = {}
        for p in root.findall(".//{*}Period"):
            start_time = datetime.strptime(p.find(".//{*}start").text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=pytz.UTC).astimezone(CET)
            for pt in p.findall(".//{*}Point"):
                pos = int(pt.find("{*}position").text) - 1
                hour = start_time.replace(hour=pos).strftime("%Y-%m-%dT%H:00")
                prices[hour] = round(float(pt.find("{*}price.amount").text) / 1000, 3)
        if len(prices) >= 47:
            logging.info(f"FULL FETCH: {len(prices)} hours{'—close enough' if len(prices) < 48 else ''}, Range: {min(prices.keys())} to {max(prices.keys())}")
            open("/tmp/full_fetch_done", "w").close()
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
    source = "ENTSO-E" if prices else "None"
    if len(prices) >= 48:
        current = prices
        min_price = min(prices.values())
        max_price = max(prices.values())
        logging.info(f"FULL FETCH: {len(prices)} hours, Min={min_price}, Max={max_price}, Source={source}")
    else:
        current.update(prices)
        logging.info(f"Partial fetch: {len(prices)} hours updated, Source={source}")
    with open(filename, "w") as f:
        json.dump({"retrieved": now_cet().isoformat(), "prices": current}, f)
    if len(prices) >= 48:
        open("/tmp/full_fetch_done", "w").close()

def main():
    if os.path.exists("/tmp/full_fetch_done"):
        os.remove("/tmp/full_fetch_done")
    logging.info("ENTSO-E fetcher initialized")
    prices = fetch_entsoe()
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
        while now_cet() < deadline and len(prices) < 47:
            prices = fetch_entsoe()
            save_prices(prices)
            if len(prices) >= 47:
                break
            logging.info("Incomplete—retrying in 5m")
            time.sleep(300)
        time.sleep(24 * 3600)

if __name__ == "__main__":
    main()