#!/usr/bin/env python3
import time
import yaml
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
log_dir = Path("/root/master_kees/logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    filename=log_dir / "mothership.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mothership")

def load_config():
    """Load config.yaml from /root/master_kees/."""
    config_path = Path("/root/master_kees/config.yaml")
    if not config_path.exists():
        logger.error("config.yaml not found!")
        raise FileNotFoundError("config.yaml missing")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def get_current_price(prices):
    """Get price percentage for the current hour."""
    now = datetime.now().strftime("%Y-%m-%dT%H:00")
    return prices.get(now, None)

def decide_heating_state(price_percent):
    """Mirror HA logic for heating (ES1-8)."""
    if price_percent is None:
        logger.warning("No price data—defaulting to ES1")
        return 1  # ES1
    if price_percent == 0:
        return 5  # ES5
    elif 1 <= price_percent <= 20:
        return 6  # ES6
    elif 20 < price_percent <= 40:
        return 3  # ES3
    elif 40 < price_percent <= 60:
        return 2  # ES2
    elif 60 < price_percent <= 80:
        return 7  # ES7
    elif 80 < price_percent < 100:
        return 8  # ES8
    elif price_percent >= 100:
        return 1  # ES1
    return 1  # Fallback

def decide_dhw_state(price_percent):
    """Mirror HA logic for DHW (on/off)."""
    if price_percent is None:
        logger.warning("No price data—defaulting to OFF")
        return False  # Off
    return price_percent <= 60  # On if <=60%, Off if >60%

def monitor_clients(config):
    """Monitor clients and log decisions."""
    price_file = Path("/root/master_kees/Dynamic_Prices/prices_percent.json")
    client_base = Path("/root/master_kees/clients")

    # Load prices
    prices = {}
    if price_file.exists():
        with open(price_file, "r") as f:
            data = yaml.safe_load(f)
            prices = data.get("prices", {})
        logger.info(f"Price data loaded: {list(prices.items())[:5]}...")
        current_price = get_current_price(prices)
        logger.info(f"Current hour price: {current_price}%")
    else:
        logger.warning("prices_percent.json not found—using defaults")
        current_price = None

    # Process each client
    for client in config.get("clients", []):
        client_path = client_base / client
        for system in ["heating", "dhw"]:
            config_path = client_path / system / "config.yaml"
            if config_path.exists():
                logger.info(f"Monitoring {client}/{system}")
                if system == "heating":
                    decision = decide_heating_state(current_price)
                    logger.info(f"{client}/{system} decision: ES{decision}")
                else:  # dhw
                    decision = decide_dhw_state(current_price)
                    logger.info(f"{client}/{system} decision: {'ON' if decision else 'OFF'}")
            else:
                logger.warning(f"{client}/{system} config missing")

def main():
    logger.info("Mothership starting...")
    config = load_config()
    logger.info("Config loaded successfully")
    logger.info("Assuming price fetchers and fuser are running independently")

    # Main loop (runs once for test)
    while True:
        try:
            monitor_clients(config)
            interval = config.get("interval", 3600)  # Default 1 hour
            logger.info(f"Cycle complete, sleeping {interval}s")
            time.sleep(interval)
            break  # Test mode
        except Exception as e:
            logger.error(f"Cycle failed: {str(e)}—retrying in 60s")
            time.sleep(60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Mothership crashed: {str(e)}")
        raise