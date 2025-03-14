#!/usr/bin/env python3
import os
import subprocess
import time
import yaml
import logging
from pathlib import Path

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

def start_price_fetchers():
    """Run Dynamic_Prices fetchers in sequence."""
    fetchers = ["tibber_fetcher.py", "entsoe_fetcher.py", "price_fuser.py"]
    base_path = Path("/root/master_kees/Dynamic_Prices")
    for fetcher in fetchers:
        fetcher_path = base_path / fetcher
        if fetcher_path.exists():
            logger.info(f"Starting {fetcher}")
            result = subprocess.run(["python3", str(fetcher_path)], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"{fetcher} completed successfully")
            else:
                logger.error(f"{fetcher} failed: {result.stderr}")
        else:
            logger.warning(f"{fetcher} not found, skipping")

def monitor_clients(config):
    """Monitor client dirs and log decisions (no control yet)."""
    client_base = Path("/root/master_kees/clients/julianalaan_39")
    price_file = Path("/root/master_kees/Dynamic_Prices/prices_percent.json")

    # Check price data
    if price_file.exists():
        with open(price_file, "r") as f:
            prices = yaml.safe_load(f)  # JSON-like structure
        logger.info(f"Price data loaded: {prices[:5]}...")  # Log first 5
    else:
        logger.warning("prices_percent.json not found in Dynamic_Prices/")
        return

    # Monitor heating and DHW
    for system in ["heating", "dhw"]:
        config_path = client_base / system / "config.yaml"
        data_dir = client_base / system / "data"
        if config_path.exists():
            logger.info(f"Monitoring {system}: simulating HA logic")
            # Placeholder: Mirror HA logic (ES1-8 for heating, on/off for DHW)
            decision = "ES3" if system == "heating" else "ON"  # Dummy decisions
            logger.info(f"{system} decision: {decision} (based on prices)")
        else:
            logger.warning(f"{system} missing config")

def main():
    logger.info("Mothership starting...")
    config = load_config()
    logger.info("Config loaded successfully")

    # Start price fetchers
    start_price_fetchers()

    # Monitor clients in a loop (runs once for test)
    while True:
        monitor_clients(config)
        logger.info("Cycle complete, sleeping 60s (test mode)")
        time.sleep(60)
        break  # One cycle for test

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Mothership crashed: {str(e)}")
        raise