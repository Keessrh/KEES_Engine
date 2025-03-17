from flask import Flask, render_template, jsonify
import json
import os
import psutil
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

BASE_DIR = '/root/master_kees'
PRICE_FILE = f"{BASE_DIR}/Dynamic_Prices/prices_percent.json"

def get_energy_state(percent):  # Your logic from mothership.py
    if percent is None: return 1
    if percent == 0: return 5  # Cheapest
    elif 1 <= percent <= 20: return 6
    elif 20 < percent <= 40: return 3
    elif 40 < percent <= 60: return 2
    elif 60 < percent <= 80: return 7
    elif 80 < percent < 100: return 8
    elif percent >= 100: return 1  # Highest
    return 1

def get_dhw_state(percent):
    if percent is None: return False
    return percent <= 60

def check_process(name):
    try:
        for proc in psutil.process_iter(['pid', 'cmdline']):
            if proc.info['cmdline'] and any(name in cmd for cmd in proc.info['cmdline']):
                return True
        return False
    except Exception:
        return False

def get_price_data():
    try:
        with open(PRICE_FILE) as f:
            data = json.load(f)
        prices = data.get("prices", {})
        now = datetime.now(pytz.timezone("Europe/Amsterdam")).strftime("%Y-%m-%dT%H:00")
        current_percent = prices.get(now, 50)
        return {
            "prices": prices,
            "current": current_percent,
            "state": get_energy_state(current_percent),
            "dhw": get_dhw_state(current_percent)
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return {"prices": {}, "current": 50, "state": 1, "dhw": False}

@app.route('/status')
def status():
    return {
        "Tibber": check_process("tibber_fetcher.py"),
        "ENTSO-E": check_process("entsoe_fetcher.py"),
        "Fuser": check_process("price_fuser.py")
    }

@app.route('/prices')
def prices():
    return jsonify(get_price_data())

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)