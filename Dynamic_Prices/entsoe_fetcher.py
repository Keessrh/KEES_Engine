#!/usr/bin/env python3
import json, logging, os, time, requests, pytz
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

API_TOKEN = "df3889a7-1758-493e-be53-dac8605fc94c"
API_URL = "https://web-api.tp.entsoe.eu/api"
REGION = "10YNL----------L"
CACHE_FILE = "/root/master_kees/Dynamic_Prices/prices_entsoe.json"
LOG_FILE = "/root/master_kees/Dynamic_Prices/logs/entsoe_fetcher.log"
CET = pytz.timezone("Europe/Amsterdam")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger()

def get_cet_now():
    return datetime.now(CET)

def fetch_entsoe_prices():
    try:
        today = get_cet_now().date()
        tomorrow = today + timedelta(days=1)
        params = {
            "securityToken": API_TOKEN,
            "documentType": "A44",
            "in_Domain": REGION,
            "out_Domain": REGION,
            "periodStart": today.strftime("%Y%m%d") + "0000",
            "periodEnd": tomorrow.strftime("%Y%m%d") + "2300"
        }
        response = requests.get(API_URL, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            prices = {}
            for period in root.findall(".//{*}Period"):
                start = datetime.strptime(period.find(".//{*}start").text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=pytz.UTC)
                start_cet = start.astimezone(CET).strftime("%Y-%m-%dT%H:00")
                for point in period.findall(".//{*}Point"):
                    pos = int(point.find("{*}position").text) - 1
                    price_mwh = float(point.find("{*}price.amount").text)
                    price_kwh = round(price_mwh / 1000, 3)
                    hour_dt = start_cet if pos == 0 else f"{start_cet[:11]}{pos:02d}:00"
                    prices[hour_dt] = price_kwh
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
    logger.info("ENTSO-E fetcher started")
    # Initial fetch on start/restart
    prices = fetch_entsoe_prices()
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
                prices = fetch_entsoe_prices()
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