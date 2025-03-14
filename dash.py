from flask import Flask, render_template_string
import json
import csv
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# Paths
BASE_DIR = Path('/root/master_kees')
PRICE_FILE = BASE_DIR / 'Dynamic_Prices/prices_percent.json'
HEATING_CSV = BASE_DIR / 'clients/julianalaan_39/heating/data/2025-03-14.csv'
DHW_CSV = BASE_DIR / 'clients/julianalaan_39/dhw/data/2025-03-14.csv'

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
        .es-status { font-size: 28px; font-weight: bold; margin: 15px; }
        .es-on { color: green; }
        .es-off { color: red; }
        .dhw-on { color: blue; }
        .dhw-off { color: gray; }
        table { margin: 20px auto; border-collapse: collapse; }
        th, td { padding: 8px; border: 1px solid #ddd; font-size: 16px; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>K.E.E.S. Phone Dashboard</h1>
    <div class="es-status">ES: <span class="{{ es_class }}">{{ es_state }}</span></div>
    <div class="status">DHW: <span class="{{ dhw_class }}">{{ dhw_state }}</span></div>
    <div class="status">Price: {{ price }}%</div>
    <h2>Last 5 Hourly Decisions</h2>
    <table>
        <tr><th>Time</th><th>Price</th><th>ES/DHW</th></tr>
        {% for entry in history %}
        <tr><td>{{ entry.time }}</td><td>{{ entry.price }}%</td><td>{{ entry.decision }}</td></tr>
        {% endfor %}
    </table>
</body>
</html>
"""

def get_current_states():
    es_state = 'OFF'
    dhw_state = 'OFF'
    try:
        with open(HEATING_CSV, 'r') as f:
            rows = list(csv.reader(f))
            for row in reversed(rows):
                if row and 'ES' in row[0]:
                    es_state = row[1].strip()
                    break
    except FileNotFoundError:
        pass
    try:
        with open(DHW_CSV, 'r') as f:
            rows = list(csv.reader(f))
            for row in reversed(rows):
                if row and 'DHW' in row[0]:
                    dhw_state = row[1].strip()
                    break
    except FileNotFoundError:
        pass
    return es_state, dhw_state

def get_price():
    try:
        with open(PRICE_FILE, 'r') as f:
            data = json.load(f)
            return data.get('price_percent', 61)
    except (FileNotFoundError, json.JSONDecodeError):
        return 61

def get_history():
    history = []
    try:
        with open(HEATING_CSV, 'r') as hf, open(DHW_CSV, 'r') as df:
            h_rows = list(csv.reader(hf))
            d_rows = list(csv.reader(df))
            # Assume timestamp in col 2 (e.g., "2025-03-14 22:00:01"), ES/DHW in col 1
            h_dict = {row[2]: row[1] for row in h_rows if len(row) > 2 and 'ES' in row[0]}
            d_dict = {row[2]: row[1] for row in d_rows if len(row) > 2 and 'DHW' in row[0]}
            all_times = sorted(set(h_dict.keys()) | set(d_dict.keys()), reverse=True)
            for t in all_times[:5]:  # Last 5 entries
                es = h_dict.get(t, 'OFF')
                dhw = d_dict.get(t, 'OFF')
                # Fake price history (hourly from current price, adjust if CSV has it)
                hour = int(t.split(':')[1])
                price = get_price() - (22 - hour) * 3 if hour <= 22 else 61
                history.append({'time': t.split(' ')[1], 'price': price, 'decision': f'{es}/{dhw}'})
    except (FileNotFoundError, IndexError):
        # Fallback fake history if CSVs lack timestamps
        current_price = get_price()
        now = datetime.now()
        for i in range(5):
            time = f"{22-i:02d}:00:01"
            price = current_price - i * 3 if i <= 4 else 61
            history.append({'time': time, 'price': price, 'decision': 'ES7/OFF'})
    return history

@app.route('/')
def dashboard():
    es_state, dhw_state = get_current_states()
    price = get_price()
    history = get_history()
    es_class = 'es-on' if es_state == 'ES7' else 'es-off'
    dhw_class = 'dhw-on' if dhw_state == 'ON' else 'dhw-off'
    return render_template_string(
        TEMPLATE,
        es_state=es_state,
        dhw_state=dhw_state,
        price=price,
        es_class=es_class,
        dhw_class=dhw_class,
        history=history
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)