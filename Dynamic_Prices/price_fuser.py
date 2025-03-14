import json
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

logging.basicConfig(filename='logs/price_fuser.log', level=logging.ERROR,
                    format='%(asctime)s: %(message)s')

class PriceWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('prices_tibber.json') or event.src_path.endswith('prices_entsoe.json'):
            print(f"Detected change in {event.src_path} - fusing prices!", flush=True)
            time.sleep(2)  # Wait 2s for fetcher to finish writing
            fuse_prices()

def fuse_prices():
    try:
        tibber, entsoe = None, None
        for _ in range(2):
            try:
                if os.path.exists('prices_tibber.json'):
                    with open('prices_tibber.json', 'r') as f:
                        tibber_data = json.load(f)
                        tibber = tibber_data.get("prices", {})
                if os.path.exists('prices_entsoe.json'):
                    with open('prices_entsoe.json', 'r') as f:
                        entsoe_data = json.load(f)
                        entsoe = entsoe_data.get("prices", {})
                if tibber and entsoe:
                    break
                raise FileNotFoundError("Missing JSON file(s)")
            except Exception as e:
                logging.error(f"Attempt failed: {str(e)}")
                time.sleep(300)

        if not tibber or not entsoe:
            if os.path.exists('prices_percent.json'):
                with open('prices_percent.json', 'r') as f:
                    last_percent = json.load(f)
                logging.warning("Using last prices_percent.json")
                return
            else:
                logging.error("No data or fallback available!")
                return

        averages = {}
        for hour in tibber:
            if hour in entsoe:
                avg = (tibber[hour] + entsoe[hour]) / 2
                averages[hour] = avg

        if averages:
            min_avg, max_avg = min(averages.values()), max(averages.values())
            percents = {
                "retrieved": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "prices": {
                    hour: int(((avg - min_avg) / (max_avg - min_avg)) * 100) if max_avg > min_avg else 50
                    for hour, avg in averages.items()
                }
            }
            with open('prices_percent.json', 'w') as f:
                json.dump(percents, f, indent=2)
    except Exception as e:
        logging.error(f"Failed: {str(e)}")

if __name__ == "__main__":
    print("Starting price fuser - initial fusion...", flush=True)
    fuse_prices()
    observer = Observer()
    observer.schedule(PriceWatcher(), path='/root/master_kees/Dynamic_Prices/', recursive=False)
    observer.start()
    print("Price fuser running... watching for updates!", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()