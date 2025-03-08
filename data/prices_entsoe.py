import requests
import logging
from datetime import datetime, timedelta
import time
from dateutil import tz
from xml.etree import ElementTree as ET

logging.basicConfig(filename="/root/new_main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

ENTSOE_API_KEY = "df3889a7-1758-493e-be53-dac8605fc94c"
ENTSOE_URL = "https://web-api.tp.entsoe.eu/api"
ENTSOE_REGION = "10YNL----------L"
CET = tz.gettz('Europe/Amsterdam')

def fetch_entsoe_prices():
    while True:
        now = datetime.now(CET)
        next_update = now.replace(hour=13, minute=0, second=0, microsecond=0)
        if now > next_update:
            next_update += timedelta(days=1)
        wait_seconds = (next_update - now).total_seconds()
        logger.info(f"Waiting until {next_update} for ENTSO-E fetch ({wait_seconds/3600:.1f} hours)")
        time.sleep(wait_seconds)

        try:
            utc_now = datetime.now(tz.UTC)
            start = utc_now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=2)
            params = {
                "securityToken": ENTSOE_API_KEY,
                "documentType": "A44",
                "in_Domain": ENTSOE_REGION,
                "out_Domain": ENTSOE_REGION,
                "periodStart": start.strftime("%Y%m%d%H00"),
                "periodEnd": end.strftime("%Y%m%d%H00")
            }
            response = requests.get(ENTSOE_URL, params=params)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                prices = {}
                for period in root.findall(".//{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}Period"):
                    start_time_str = period.find("{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}timeInterval/{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}start").text
                    start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=tz.UTC)
                    for point in period.findall("{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}Point"):
                        position = int(point.find("{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}position").text)
                        price_elem = point.find("{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}price.amount")
                        if price_elem is None:
                            continue
                        price = float(price_elem.text) / 1000  # €/MWh to €/kWh
                        hour = start_time + timedelta(hours=position - 1)
                        hour_cet = hour.astimezone(CET)
                        prices[hour_cet.strftime("%Y-%m-%dT%H:00:00.000+01:00")] = price
                current_hour = now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00.000+01:00")
                current_price = prices.get(current_hour, 0.05)
                logger.info(f"ENTSO-E prices fetched: {current_price} €/kWh at {current_hour}")
                with open("/root/master_kees/prices_test.json", "r+") as f:
                    data = json.load(f) if os.path.getsize("/root/master_kees/prices_test.json") > 0 else {}
                    data["entsoe"] = {"timestamp": now.isoformat(), "prices": prices}
                    f.seek(0)
                    json.dump(data, f)
            else:
                logger.error(f"ENTSO-E fetch failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"ENTSO-E fetch error: {str(e)}")
        time.sleep(300)
