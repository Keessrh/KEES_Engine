import requests
import logging
import json
from datetime import datetime, timedelta
from dateutil import tz
import time

# Log to test file
logging.basicConfig(filename="/root/new_main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

TIBBER_API_KEY = "BxfErG_8Ps08ymt3hOkrZmIkNjSj92VCT638Q5DVo24"
TIBBER_URL = "https://api.tibber.com/v1-beta/gql"
TIBBER_QUERY = """
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
CET = tz.gettz('Europe/Amsterdam')

def fetch_tibber_prices():
    while True:
        now = datetime.now(CET)
        next_update = now.replace(hour=13, minute=0, second=0, microsecond=0)
        if now > next_update:
            next_update += timedelta(days=1)
        wait_seconds = (next_update - now).total_seconds()
        logger.info(f"Waiting until {next_update} for Tibber fetch ({wait_seconds/3600:.1f} hours)")
        time.sleep(wait_seconds)

        try:
            headers = {"Authorization": f"Bearer {TIBBER_API_KEY}", "Content-Type": "application/json"}
            response = requests.post(TIBBER_URL, json={"query": TIBBER_QUERY}, headers=headers)
            if response.status_code == 200:
                data = response.json()
                today = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"]
                tomorrow = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["tomorrow"] or []
                prices = {item["startsAt"].replace("Z", "+01:00"): item["total"] for item in today + tomorrow}
                current_hour = now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00.000+01:00")
                current_price = prices.get(current_hour, 0.05)
                logger.info(f"Tibber prices fetched: {current_price} €/kWh at {current_hour}")
                with open("/root/master_kees/prices_test.json", "w") as f:
                    json.dump({"tibber": {"timestamp": now.isoformat(), "prices": prices}}, f)
            else:
                logger.error(f"Tibber fetch failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Tibber fetch error: {str(e)}")
        time.sleep(300)