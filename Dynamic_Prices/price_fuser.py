#!/usr/bin/env python3
import json, logging, os, signal, time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
        avg = {h: (tibber[h] + entsoe[h]) / 2 for h in tibber if h in entsoe}
        if avg:
            min_a, max_a = min(avg.values()), max(avg.values())
            percents = {"retrieved": time.strftime("%Y-%m-%dT%H:%M:%S"), 
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
    while True: time.sleep(1)