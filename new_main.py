import threading
import logging
import yaml
from data.prices_tibber import fetch_tibber_prices
from clients.julianalaan_39.heatpump import run_heatpump

logging.basicConfig(filename="/root/new_main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

with open("/root/master_kees/config.yaml", "r") as f:
    config = yaml.safe_load(f)

if __name__ == "__main__":
    logger.info("Starting NEW K.E.E.S. Engine (test mode)")
    threading.Thread(target=fetch_tibber_prices, daemon=True).start()
    threading.Thread(target=run_heatpump, daemon=True).start()
    logger.info("New engine running—testing safely with heatpump!")
    while True:
        pass
