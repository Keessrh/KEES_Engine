#!/usr/bin/env python3

import time
import json
import logging
import requests
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import pytz
import os

# Constants
API_TOKEN = "df3889a7-1758-493e-be53-dac8605fc94c"
API_URL = "https://web-api.tp.entsoe.eu/api"
REGION = "10YNL----------L"
CACHE_FILE = "/root/master_kees/Dynamic_Prices/prices.json"  # Updated path
LOG_FILE = "/root/main.log"
MQTT_BROKER = "159.223.10.31"
MQTT_PORT = 1883
MQTT_TOPIC = "prices/entsoe/current"
DEFAULT_PRICE = 0.05  # €/kWh fallback
CET = pytz.timezone("Europe/Amsterdam")

# Logging setup
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def get_cet_time():
    return datetime.now(CET)

def fetch_entsoe_prices():
    tomorrow = (get_cet_time() + timedelta(days=1)).date()
    period_start = tomorrow.strftime("%Y%m%d") + "0000"
    period_end = tomorrow.strftime("%Y%m%d") + "2300"
    
    params = {
        "securityToken": API_TOKEN,
        "documentType": "A44",
        "in_Domain": REGION,
        "out_Domain": REGION,
        "periodStart": period_start,
        "periodEnd": period_end
    }
    
    for attempt in range(3):
        try:
            response = requests.get(API_URL, params=params, timeout=10)
            if response.status_code == 200:
                data = response.text  # XML response
                prices = parse_entsoe_xml(data)
                if prices and any(k.startswith(tomorrow.strftime("%Y-%m-%d")) for k in prices):
                    logging.info(f"ENTSO-E fetched: {len(prices)} prices for {tomorrow}")
                    return prices
                else:
                    logging.warning("ENTSO-E returned no prices for tomorrow")
            else:
                logging.warning(f"ENTSO-E failed: HTTP {response.status_code}")
        except Exception as e:
            logging.error(f"ENTSO-E failed: {str(e)}")
        
        if attempt < 2:
            time.sleep(300)  # 5 min retry delay
    return None

def parse_entsoe_xml(xml_data):
    prices = {}
    try:
        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_data)
        for period in root.findall(".//{*}Period"):
            start = period.find(".//{*}start").text
            start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%MZ").replace(tzinfo=pytz.UTC)
            start_cet = start_dt.astimezone(CET).strftime("%Y-%m-%dT%H:%M:00+01:00")
            for point in period.findall(".//{*}Point"):
                pos = int(point.find("{*}position").text) - 1
                price_mwh = float(point.find("{*}price.amount").text)
                price_kwh = price_mwh / 1000  # Convert to €/kWh
                hour_dt = start_cet[:11] + f"{pos:02d}" + start_cet[13:]
                prices[hour_dt] = price_kwh
        return prices
    except Exception as e:
        logging.error(f"XML parsing failed: {str(e)}")
        return {}

def load_cached_prices():
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            return data.get("entsoe", {}).get("prices", {})
    except Exception:
        logging.warning("No valid cache found")
        return {}

def save_prices(prices):
    timestamp = datetime.utcnow().isoformat() + "+00:00"
    data = {
        "entsoe": {
            "timestamp": timestamp,
            "source": "ENTSO-E",
            "prices": prices
        }
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    logging.info(f"Prices saved to {CACHE_FILE}")

def publish_mqtt(price):
    try:
        client = mqtt.Client()
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        payload = json.dumps({"price": price})
        client.publish(MQTT_TOPIC, payload, qos=1)
        client.disconnect()
        logging.info(f"Published to MQTT: {payload}")
    except Exception as e:
        logging.error(f"MQTT publish failed: {str(e)}")

def get_current_hour_price(prices):
    now = get_cet_time()
    hour_key = now.strftime("%Y-%m-%dT%H:00:00+01:00")
    return prices.get(hour_key, DEFAULT_PRICE)

def main():
    last_mqtt_hour = None
    while True:
        now = get_cet_time()
        today_13_00 = now.replace(hour=13, minute=0, second=0, microsecond=0)
        today_13_30 = now.replace(hour=13, minute=30, second=0, microsecond=0)
        today_14_00 = now.replace(hour=14, minute=0, second=0, microsecond=0)
        
        # Check if we have tomorrow's prices
        cached_prices = load_cached_prices()
        tomorrow = (now + timedelta(days=1)).date().isoformat()
        has_tomorrow = any(k.startswith(tomorrow) for k in cached_prices)
        
        if not has_tomorrow and now >= today_13_00 and now < today_14_00:
            # Fetching window
            if now < today_13_30:
                interval = 5 * 60  # 5 min checks 13:00–13:30
            else:
                interval = 15 * 60  # 15 min checks 13:30–14:00
            
            prices = fetch_entsoe_prices()
            if prices:
                save_prices(prices)
                cached_prices = prices
            else:
                logging.info("Using cached prices after retries")
        
        # MQTT publishing
        current_hour = now.strftime("%H")
        if cached_prices and (last_mqtt_hour != current_hour):
            price = get_current_hour_price(cached_prices)
            publish_mqtt(price)
            last_mqtt_hour = current_hour
        
        # Sleep logic
        if has_tomorrow:
            next_run = today_13_00 + timedelta(days=1)
            sleep_time = (next_run - now).total_seconds()
            logging.info(f"Tomorrow's prices fetched, sleeping until {next_run}")
        elif now < today_13_00:
            sleep_time = (today_13_00 - now).total_seconds()
            logging.info(f"Before 13:00, sleeping until {today_13_00}")
        elif now >= today_14_00:
            next_run = today_13_00 + timedelta(days=1)
            sleep_time = (next_run - now).total_seconds()
            logging.info(f"After 14:00, no prices, sleeping until {next_run}")
        else:
            sleep_time = interval
        
        time.sleep(min(sleep_time, 3600))  # Cap at 1 hour for responsiveness

if __name__ == "__main__":
    logging.info("Starting ENTSO-E price fetcher")
    main()