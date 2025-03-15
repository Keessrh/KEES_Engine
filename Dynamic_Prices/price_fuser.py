#!/usr/bin/env python3
import json, logging, os, signal, time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timedelta
import pytz

CET = pytz.timezone("Europe/Amsterdam")
logging.basicConfig(filename='logs/price_fuser.log', level=logging.INFO, format='%(asctime)s - %(message)s')

def signal_handler(signum, frame):
    logging.info("Entropy claims us")
    observer.stop()
    exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

class Watcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(('prices_tibber.json', 'prices_entsoe.json')):
            logging.info(f"Change in {event.src_path}")
            time.sleep(2)
            fuse()

def now_cet():
    return datetime.now(CET)

def fuse():
    try:
        tibber = entsoe = {}
        if os.path.exists('prices_tibber.json'):
            with open('prices_tibber.json') as f: tibber = json.load(f).get("prices", {})
        if os.path.exists('prices_entsoe.json'):
            with open('prices_entsoe.json') as f: entsoe = json.load(f).get("prices", {})
        if not (tibber and entsoe):
            logging.warning("Missing data—holding last fusion")
            return
        # Force 34hr: 15T00:00 - 16T23:00 (dynamic later)
        start = datetime(2025, 3, 15, 0, 0, tzinfo=CET)
        end = datetime(2025, 3, 16, 23, 0, tzinfo=CET)
        avg = {h: (tibber[h] + entsoe[h]) / 2 for h in tibber if h in entsoe and start.strftime('%Y-%m-%dT%H:00') <= h <= end.strftime('%Y-%m-%dT%H:00')}
        if not avg:
            logging.warning("No data in 34hr window")
            return
        min_a, max_a = min(avg.values()), max(avg.values())
        logging.info(f"Min: {min_a}, Max: {max_a}, 13:00: {avg.get('2025-03-15T13:00')}, 17:00: {avg.get('2025-03-15T17:00')}, 18:00: {avg.get('2025-03-15T18:00')}")
        percents = {"retrieved": now_cet().strftime("%Y-%m-%dT%H:%M:%S"), 
                   "prices": {h: int(100 * (a - min_a) / (max_a - min_a)) if max_a > min_a else 50 for h, a in avg.items()}}
        with open('prices_percent.json', 'w') as f: json.dump(percents, f)
        logging.info(f"Fused {len(percents['prices'])} hours")
    except Exception as e:
        logging.error(f"Fusion failed: {e}")

if __name__ == "__main__":
    logging.info("Fuser begins")
    fuse()
    observer = Observer()
    observer.schedule(Watcher(), path='.', recursive=False)
    observer.start()
    logging.info("Watching")
    while True: time.slee