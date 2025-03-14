from flask import Flask, render_template_string
import json
import csv
from pathlib import Path

app = Flask(__name__)

# Paths
BASE_DIR = Path('/root/master_kees')
PRICE_FILE = BASE_DIR / 'Dynamic_Prices/prices_percent.json'
DATA_FILE = BASE_DIR / 'data/2025-03-14.csv'

# HTML template
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>K.E.E.S. Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 20px; }
        h1 { font-size: 24px; }
        .status { font-size: 18px; margin: 10px; }
        .es-on { color: green; }
        .es-off { color: red; }
        .dhw-on { color: blue; }
        .dhw-off { color: gray; }
    </style>
</head>
<body>
    <h1>K.E.E.S. Phone Dashboard</h1>
    <div class="status">ES: <span class="{{ es_class }}">{{ es_state }}</span></div>
    <div class="status">DHW: <span class="{{ dhw_class }}">{{ dhw_state }}</span></div>
    <div class="status">Price: {{ price }}%</div>
</body>
</html>
"""

def get_latest_states():
    es_state = 'OFF'
    dhw_state = 'OFF'
    try:
        with open(DATA_FILE, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
            for row in reversed(rows):  # Latest entry first
                if row and 'ES' in row[0]:
                    es_state = row[1].strip()
                    break
            for row in reversed(rows):
                if row and 'DHW' in row[0]:
                    dhw_state = row[1].strip()
                    break
    except FileNotFoundError:
        pass  # Defaults to OFF if file’s missing
    return es_state, dhw_state

def get_price():
    try:
        with open(PRICE_FILE, 'r') as f:
            data = json.load(f)
            return data.get('price_percent', 61)  # Fallback to 61% if key’s missing
    except (FileNotFoundError, json.JSONDecodeError):
        return 61  # Default if file’s busted

@app.route('/')
def dashboard():
    es_state, dhw_state = get_latest_states()
    price = get_price()
    es_class = 'es-on' if es_state == 'ES7' else 'es-off'
    dhw_class = 'dhw-on' if dhw_state == 'ON' else 'dhw-off'
    return render_template_string(
        TEMPLATE,
        es_state=es_state,
        dhw_state=dhw_state,
        price=price,
        es_class=es_class,
        dhw_class=dhw_class
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)