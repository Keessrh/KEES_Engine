from flask import Flask, render_template_string
import json
import csv
from pathlib import Path

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
            es_state = rows[-1][4].strip() if rows else 'OFF'  # Last row, col 4
    except (FileNotFoundError, IndexError):
        pass
    try:
        with open(DHW_CSV, 'r') as f:
            rows = list(csv.reader(f))
            dhw_state = rows[-1][4].strip() if rows else 'OFF'  # Last row, col 4
    except (FileNotFoundError, IndexError):
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
    history = {}
    try:
        # Load heating data (hourly only)
        with open(HEATING_CSV, 'r') as hf:
            h_rows = [row for row in csv.reader(hf) if len(row) > 4 and ":00:01" in row[0]]
            for row in h_rows:
                time = row[0].split('T')[1].split('.')[0]  # "22:00:01"
                history[time] = {'price': row[1], 'es': row[4], 'dhw': 'OFF'}
        # Overlay DHW data
        with open(DHW_CSV, 'r') as df:
            d_rows = [row for row in csv.reader(df) if len(row) > 4 and ":00:01" in row[0]]
            for row in d_rows:
                time = row[0].split('T')[1].split('.')[0]
                if time in history:
                    history[time]['dhw'] = row[4]
                else:
                    history[time] = {'price': row[1], 'es': 'OFF', 'dhw': row[4]}
        # Format last 5
        result = [
            {'time': t, 'price': data['price'], 'decision': f"{data['es']}/{data['dhw']}"}
            for t, data in sorted(history.items(), reverse=True)[:5]
        ]
        return result[::-1] if result else []  # Oldest first, empty if no hourly data
    except (FileNotFoundError, IndexError):
        return []  # No fallback unless explicitly wanted

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