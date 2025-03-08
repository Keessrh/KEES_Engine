import paho.mqtt.client as mqtt
import json
import os
import importlib
from flask import Flask, render_template_string
import requests
from datetime import datetime, timedelta
import logging
import collections
import threading
import time
from dateutil import tz
from xml.etree import ElementTree as ET

app = Flask(__name__)

logging.basicConfig(filename="/root/main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

client = mqtt.Client()
MQTT_BROKER = "159.223.10.31"
MQTT_PORT = 1883
client.connect(MQTT_BROKER, MQTT_PORT)
logger.info("Connected to MQTT broker")

TIBBER_API_KEY = "BxfErG_8Ps08ymt3hOkrZmIkNjSj92VCT638Q5DVo24"
TIBBER_URL = "https://api.tibber.com/v1-beta/gql"
TIBBER_QUERY = """
{
  viewer {
    homes {
      currentSubscription {
        priceInfo {
          today { total startsAt }
          tomorrow { total startsAt }
        }
      }
    }
  }
}
"""
ENTSOE_API_KEY = "df3889a7-1758-493e-be53-dac8605fc94c"
ENTSOE_URL = "https://web-api.tp.entsoe.eu/api"
ENTSOE_REGION = "10YNL----------L"

huizen = {}
client_modules = {}
current_price = 0.05
price_source = "Fallback"
price_dict = {}
entsoe_price_dict = {}
last_price_update = None
last_entsoe_update = None
cop_buffer = collections.deque(maxlen=1440)
CET = tz.gettz('Europe/Amsterdam')

def get_tibber_prices():
    try:
        headers = {"Authorization": f"Bearer {TIBBER_API_KEY}", "Content-Type": "application/json"}
        response = requests.post(TIBBER_URL, json={"query": TIBBER_QUERY}, headers=headers)
        if response.status_code == 200:
            data = response.json()
            today = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"]
            tomorrow = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["tomorrow"] or []
            prices = {item["startsAt"].replace("Z", "+01:00"): item["total"] for item in today + tomorrow}
            now = datetime.now(CET)
            current_hour = now.replace(minute=0, second=0, microsecond=0)
            current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
            current_price = prices.get(current_hour_str, 0.05)
            logger.info(f"Tibber prijzen opgehaald: {len(today)} vandaag, {len(tomorrow)} morgen, huidige prijs: {current_price} op {current_hour_str}")
            return {"source": "Tibber", "price": current_price, "prices": prices, "timestamp": now.isoformat()}
        logger.error(f"Tibber fout: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        logger.error(f"Tibber exception: {str(e)}")
        return None

def get_entsoe_prices():
    try:
        now = datetime.now(tz.UTC)  # UTC voor API-aanroep
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=2)
        params = {
            "securityToken": ENTSOE_API_KEY,
            "documentType": "A44",
            "in_Domain": ENTSOE_REGION,
            "out_Domain": ENTSOE_REGION,
            "periodStart": start.strftime("%Y%m%d%H00"),
            "periodEnd": end.strftime("%Y%m%d%H00")
        }
        logger.info(f"ENTSO-E API aanroep met params: {params}")
        response = requests.get(ENTSOE_URL, params=params)
        logger.info(f"ENTSO-E response status: {response.status_code}")
        logger.debug(f"ENTSO-E response content: {response.text[:1000]}")  # Beperk tot 1000 tekens

        if response.status_code == 200:
            root = ET.fromstring(response.content)
            prices = {}
            for period in root.findall(".//{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}Period"):
                start_time_str = period.find("{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}timeInterval/{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}start").text
                start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=tz.UTC)
                logger.debug(f"Period start_time: {start_time}")
                for point in period.findall("{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}Point"):
                    position = int(point.find("{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}position").text)
                    price_elem = point.find("{urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3}price.amount")
                    if price_elem is None:
                        logger.warning(f"Geen price.amount voor position {position}")
                        continue
                    price = float(price_elem.text) / 1000  # €/MWh naar €/kWh
                    hour = start_time + timedelta(hours=position - 1)
                    hour_cet = hour.astimezone(CET)  # Converteer naar CET
                    prices[hour_cet.strftime("%Y-%m-%dT%H:00:00.000+01:00")] = price
                    logger.debug(f"Prijs toegevoegd: {hour_cet} -> {price}")
            if not prices:
                logger.warning("Geen prijzen gevonden in ENTSO-E response")
            current_hour = now.replace(minute=0, second=0, microsecond=0).astimezone(CET)
            current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
            current_price = prices.get(current_hour_str, 0.05)
            logger.info(f"ENTSO-E prijzen opgehaald: {len(prices)} totaal, huidige prijs: {current_price} op {current_hour_str}")
            return {"source": "ENTSO-E", "price": current_price, "prices": prices, "timestamp": now.isoformat()}
        logger.error(f"ENTSO-E fout: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        logger.error(f"ENTSO-E exception: {str(e)}")
        return None

def update_prices(force=False):
    global current_price, price_source, price_dict, last_price_update
    price_data = get_tibber_prices()
    if price_data:
        if not last_price_update or price_data["timestamp"] > last_price_update:
            current_price = price_data["price"]
            price_source = price_data["source"]
            price_dict = price_data["prices"]
            last_price_update = price_data["timestamp"]
            logger.info(f"Tibber prijzen geüpdatet: {current_price} €/kWh op {last_price_update}")
            with open("/root/master_kees/prices.json", "w") as f:
                json.dump({"tibber": {"timestamp": last_price_update, "source": price_source, "prices": price_dict},
                           "entsoe": {"timestamp": last_entsoe_update, "source": "ENTSO-E", "prices": entsoe_price_dict}}, f)
    elif not force:
        current_price = 0.05
        price_source = "Fallback"
        logger.warning("Tibber prijs ophalen mislukt, fallback naar 0.05 €/kWh")
    return price_data

def update_entsoe_prices(force=False):
    global entsoe_price_dict, last_entsoe_update
    price_data = get_entsoe_prices()
    if price_data:
        if not last_entsoe_update or price_data["timestamp"] > last_entsoe_update:
            entsoe_price_dict = price_data["prices"]
            last_entsoe_update = price_data["timestamp"]
            logger.info(f"ENTSO-E prijzen geüpdatet op {last_entsoe_update}")
            with open("/root/master_kees/prices.json", "w") as f:
                json.dump({"tibber": {"timestamp": last_price_update, "source": price_source, "prices": price_dict},
                           "entsoe": {"timestamp": last_entsoe_update, "source": "ENTSO-E", "prices": entsoe_price_dict}}, f)
    return price_data

def schedule_price_update():
    while True:
        now = datetime.now(CET)
        next_update = now.replace(hour=13, minute=0, second=0, microsecond=0)
        if now > next_update:
            next_update += timedelta(days=1)
        wait_seconds = (next_update - now).total_seconds()
        logger.info(f"Wachten tot {next_update} voor prijscheck ({wait_seconds/3600:.1f} uur)")
        time.sleep(wait_seconds)

        while True:
            tibber_data = update_prices(force=True)
            entsoe_data = update_entsoe_prices(force=True)
            if (tibber_data and any((now + timedelta(days=1)).strftime('%Y-%m-%d') in k for k in tibber_data["prices"])) and \
               (entsoe_data and any((now + timedelta(days=1)).strftime('%Y-%m-%d') in k for k in entsoe_data["prices"])):
                logger.info("Tomorrow prijzen ontvangen voor beide bronnen, wachten tot morgen 13:00")
                break
            logger.info("Geen tomorrow prijzen voor een bron, wachten 5 minuten")
            time.sleep(300)

def calculate_cop(power, temp_in, temp_out, flow):
    try:
        power = float(power or 0)
        temp_in = float(temp_in or 0)
        temp_out = float(temp_out or 0)
        flow = float(flow or 0)
        if power <= 0 or flow <= 0 or temp_out <= temp_in:
            logger.debug(f"COP niet berekend: power={power}, flow={flow}, temp_out={temp_out}, temp_in={temp_in}")
            return 0.0
        heat_output = (flow * (temp_out - temp_in) * 4.18) / 60
        cop = heat_output / (power / 1000)
        logger.info(f"COP berekend: {cop:.2f}")
        return cop
    except Exception as e:
        logger.error(f"COP berekening fout: {str(e)}")
        return 0.0

def update_cop_24h():
    global cop_buffer
    while True:
        now = datetime.now(CET)
        for huis_id in huizen:
            for device_name in huizen[huis_id]:
                huis_data = huizen[huis_id][device_name]
                while cop_buffer and (now - cop_buffer[0][0]) > timedelta(hours=24):
                    cop_buffer.popleft()
                if cop_buffer:
                    valid_cops = [cop for timestamp, cop in cop_buffer if cop > 0]
                    if valid_cops:
                        huis_data["cop_24h"] = sum(valid_cops) / len(valid_cops)
                    else:
                        huis_data["cop_24h"] = 0.0
                else:
                    huis_data["cop_24h"] = 0.0
        time.sleep(60)

def load_clients():
    client_dir = "/root/master_kees/clients"
    if not os.path.exists(client_dir):
        logger.error(f"Directory {client_dir} bestaat niet")
        return
    for client_name in os.listdir(client_dir):
        client_path = os.path.join(client_dir, client_name)
        if os.path.isdir(client_path):
            huizen[client_name] = {}
            client_modules[client_name] = {}
            for device_file in os.listdir(client_path):
                if device_file.endswith(".py"):
                    device_name = device_file[:-3]
                    try:
                        module = importlib.import_module(f"clients.{client_name}.{device_name}")
                        client_modules[client_name][device_name] = module
                        huis_data = module.get_data()
                        huis_data["cop_24h"] = 0.0
                        huizen[client_name][device_name] = huis_data
                    except Exception as e:
                        logger.error(f"Fout bij laden {client_name}/{device_name}: {str(e)}")

def on_message(client, userdata, msg):
    global cop_buffer
    logger.info(f"Received: {msg.topic} - {msg.payload}")
    parts = msg.topic.split("/")
    if len(parts) >= 2:
        huis_id = parts[0]
        if parts[1] == "telemetry" and huis_id in client_modules:
            payload = json.loads(msg.payload.decode())
            for device_name, module in client_modules[huis_id].items():
                huis_data = huizen[huis_id][device_name]
                for key in huis_data:
                    if key not in ["price", "cop", "cop_24h", "energy_state_input_holding"]:
                        huis_data[key] = float(payload.get(key, huis_data[key]))
                if huis_data.get("compressor_status") == 1:
                    cop = calculate_cop(
                        huis_data.get("sdm120_watt", 0),
                        huis_data.get("water_inlet_temp", 0),
                        huis_data.get("water_outlet_temp", 0),
                        huis_data.get("current_flow_rate", 0)
                    )
                    huis_data["cop"] = cop
                    if cop > 0:
                        cop_buffer.append((datetime.now(CET), cop))
                else:
                    huis_data["cop"] = 0.0
                huizen[huis_id][device_name] = huis_data
        elif parts[1] == "command" and huis_id in client_modules:
            payload = json.loads(msg.payload.decode())
            for device_name, module in client_modules[huis_id].items():
                module.process_data(msg.topic, json.dumps(payload))

def force_state():
    while True:
        now = datetime.now(CET)
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
        current_price = price_dict.get(current_hour_str, 0.05)  # Alleen Tibber voor sturing
        for huis_id in huizen:
            state = 5 if current_price <= 0.15 else 4 if current_price <= 0.25 else 3 if current_price <= 0.35 else 2
            client.publish(f"{huis_id}/command", json.dumps({"energy_state_input_holding": state}))
            logger.debug(f"Force state: {huis_id}/command - state={state}")
        time.sleep(5)

@app.route("/")
def index():
    now = datetime.now(CET)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    tibber_price = price_dict.get(current_hour_str, 0.05)
    entsoe_price = entsoe_price_dict.get(current_hour_str, 0.05)
    prev_hour = current_hour - timedelta(hours=1)
    next_hour = current_hour + timedelta(hours=1)
    prev_hour_str = prev_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    next_hour_str = next_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    tibber_prev = price_dict.get(prev_hour_str, 0.05)
    tibber_next = price_dict.get(next_hour_str, 0.05)
    entsoe_prev = entsoe_price_dict.get(prev_hour_str, 0.05)
    entsoe_next = entsoe_price_dict.get(next_hour_str, 0.05)
    prev_time = prev_hour.strftime("%a %H:%M")
    current_time = current_hour.strftime("%a %H:%M")
    next_time = next_hour.strftime("%a %H:%M")
    tibber_tomorrow = any((now + timedelta(days=1)).strftime('%Y-%m-%d') in k for k in price_dict)
    entsoe_tomorrow = any((now + timedelta(days=1)).strftime('%Y-%m-%d') in k for k in entsoe_price_dict)
    tibber_update = last_price_update if last_price_update else "Onbekend"
    entsoe_update = last_entsoe_update if last_entsoe_update else "Onbekend"

    html = """
    <h1>K.E.E.S. Control</h1>
    <p><b>Prijs Status:</b></p>
    <p>Tibber - Laatste Update: {{ tibber_update }} | Tomorrow Prijzen Bekend: {{ 'Ja' if tibber_tomorrow else 'Nee' }}</p>
    <p>ENTSO-E - Laatste Update: {{ entsoe_update }} | Tomorrow Prijzen Bekend: {{ 'Ja' if entsoe_tomorrow else 'Nee' }}</p>
    <div id="dashboard"></div>
    <script>
        function updateDashboard() {
            fetch('/data')
                .then(response => response.json())
                .then(data => {
                    let html = '';
                    for (let huis_id in data.huis_data) {
                        for (let device_name in data.huis_data[huis_id]) {
                            let huis = data.huis_data[huis_id][device_name];
                            let state = huis.energy_state_input_holding || 8;
                            let opwek = huis.opwek || 0;
                            let price = huis.price || 0.05;
                            let entsoe_price = huis.entsoe_price || 0.05;
                            let temp_in = huis.water_inlet_temp || 0;
                            let temp_out = huis.water_outlet_temp || 0;
                            let flow = huis.current_flow_rate || 0;
                            let outdoor_temp = huis.outdoor_air_temp || 0;
                            let power = huis.sdm120_watt || 0;
                            let cop = huis.cop || 0;
                            let cop_24h = huis.cop_24h || 0;
                            let compressor = huis.compressor_status || 0;
                            let dhw = huis.dhw_heating_status || 0;
                            let dhw_target = huis.dhw_target_temp || 0;
                            let target_temp = huis.target_temp_circuit1 || 0;
                            let overschot = opwek - power;
                            let savings = ((0.25 - price) * (power / 1000)).toFixed(2);
                            let decision = "State 8: Normaal verbruik";
                            if (price <= 0.15 || opwek > 2500) decision = "State 5: Laag tarief of overschot > 2500W";
                            else if (price <= 0.25 || opwek > 1500) decision = "State 4: Matig tarief of overschot > 1500W";
                            else if (price <= 0.35) decision = "State 3: Normaal tarief";
                            else decision = "State 2: Hoog tarief";
                            html += `
                                <h3>${huis_id} - ${device_name}</h3>
                                <input type='range' min='1' max='8' value='${state}' onchange='fetch("/set_state/${huis_id}/${device_name}/"+this.value)'>
                                <p><b>Live Waarden:</b></p>
                                <p>Laatste Update: ${data.current_time}</p>
                                <p>Prijs Vorige Uur (${data.prev_time}): {{ tibber_prev|round(2) }} €/kWh (Tibber) | {{ entsoe_prev|round(2) }} €/kWh (ENTSO-E)</p>
                                <p>Prijs Nu (${data.current_time_price}): ${price.toFixed(2)} €/kWh (Tibber) | ${entsoe_price.toFixed(2)} €/kWh (ENTSO-E)</p>
                                <p>Prijs Volgende Uur (${data.next_time}): {{ tibber_next|round(2) }} €/kWh (Tibber) | {{ entsoe_next|round(2) }} €/kWh (ENTSO-E)</p>
                                <p>Opwek: ${opwek} W | Verbruik: ${power} W | Overschot: ${overschot} W</p>
                                <p>Temp In: ${temp_in.toFixed(1)}°C | Temp Out: ${temp_out.toFixed(1)}°C</p>
                                <p>Stroom (Flow): ${flow.toFixed(1)} l/min | Buitentemp: ${outdoor_temp.toFixed(1)}°C</p>
                                <p>COP: ${cop.toFixed(2)} | COP 24h: ${cop_24h.toFixed(2)} | Compressor: ${compressor ? "Aan" : "Uit"}</p>
                                <p>DHW: ${dhw ? "Aan" : "Uit"} | DHW Doel: ${dhw_target.toFixed(1)}°C</p>
                                <p>Doeltemp Circuit 1: ${target_temp.toFixed(1)}°C</p>
                                <p><b>Besparing:</b> €${savings} per uur (vs 0.25 €/kWh)</p>
                                <p><b>Beslissing:</b> ${decision}</p>
                            `;
                        }
                    }
                    document.getElementById('dashboard').innerHTML = html;
                });
        }
        setInterval(updateDashboard, 5000);
        updateDashboard();
    </script>
    """
    return render_template_string(html, tibber_prev=tibber_prev, tibber_next=tibber_next, entsoe_prev=entsoe_prev, entsoe_next=entsoe_next,
                                 prev_time=prev_time, current_time=current_time, next_time=next_time,
                                 tibber_update=tibber_update, entsoe_update=entsoe_update,
                                 tibber_tomorrow=tibber_tomorrow, entsoe_tomorrow=entsoe_tomorrow)

@app.route("/data")
def data():
    now = datetime.now(CET)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    current_price = price_dict.get(current_hour_str, 0.05)
    entsoe_price = entsoe_price_dict.get(current_hour_str, 0.05)
    prev_hour = current_hour - timedelta(hours=1)
    next_hour = current_hour + timedelta(hours=1)
    prev_hour_str = prev_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    next_hour_str = next_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    prev_price = price_dict.get(prev_hour_str, 0.05)
    next_price = price_dict.get(next_hour_str, 0.05)
    entsoe_prev = entsoe_price_dict.get(prev_hour_str, 0.05)
    entsoe_next = entsoe_price_dict.get(next_hour_str, 0.05)
    prev_time = prev_hour.strftime("%a %H:%M")
    current_time = current_hour.strftime("%a %H:%M")
    next_time = next_hour.strftime("%a %H:%M")
    try:
        for huis_id in huizen:
            for device_name in huizen[huis_id]:
                huis_data = huizen[huis_id][device_name]
                huis_data["price"] = current_price
                huis_data["entsoe_price"] = entsoe_price
                state = 5 if current_price <= 0.15 else 4 if current_price <= 0.25 else 3 if current_price <= 0.35 else 2
                huis_data["energy_state_input_holding"] = state
        return json.dumps({
            "huis_data": huizen,
            "current_time": now.strftime("%a, %d %b %Y %H:%M:%S CET"),
            "prev_time": prev_time,
            "current_time_price": current_time,
            "next_time": next_time,
            "tibber_prev": prev_price,
            "tibber_next": next_price,
            "entsoe_prev": entsoe_prev,
            "entsoe_next": entsoe_next
        })
    except Exception as e:
        logger.error(f"Data route error: {str(e)}")
        return json.dumps({"error": str(e)}), 500

@app.route("/set_state/<huis_id>/<device_name>/<int:state>")
def set_state(huis_id, device_name, state):
    if huis_id in client_modules and device_name in client_modules[huis_id]:
        client_modules[huis_id][device_name].process_data(f"{huis_id}/command", json.dumps({"energy_state_input_holding": state}))
        client.publish(f"{huis_id}/command", json.dumps({"energy_state_input_holding": state}))
        logger.info(f"State handmatig ingesteld: {huis_id}/{device_name} naar {state}")
    return "State set!"

client.on_message = on_message
load_clients()
for huis_id in huizen:
    client.subscribe(f"{huis_id}/telemetry")
    client.subscribe(f"{huis_id}/command")
    logger.info(f"Subscribed to {huis_id}/telemetry and {huis_id}/command")

state_thread = threading.Thread(target=force_state, daemon=True)
state_thread.start()
price_thread = threading.Thread(target=schedule_price_update, daemon=True)
price_thread.start()
cop_thread = threading.Thread(target=update_cop_24h, daemon=True)
cop_thread.start()

update_prices()
update_entsoe_prices()
client.loop_start()
app.run(host="0.0.0.0", port=80)