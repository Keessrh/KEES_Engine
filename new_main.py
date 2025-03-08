@app.route("/")
def index():
    logger.info("Entering index route")
    logger.info(f"Rendering index, huizen: {huizen}")
    now = datetime.now(CET)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    current_hour_str = current_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    prices_file = "/root/master_kees/prices.json"
    try:
        with open(prices_file, "r") as f:
            price_data = json.load(f) if os.path.getsize(prices_file) > 0 else {"tibber": {"timestamp": "N/A", "prices": {}}, "entsoe": {"timestamp": "N/A", "prices": {}}}
    except Exception as e:
        logger.error(f"Error reading prices.json: {str(e)}")
        price_data = {"tibber": {"timestamp": "N/A", "prices": {}}, "entsoe": {"timestamp": "N/A", "prices": {}}}
    tibber_data = price_data.get("tibber", {"timestamp": "N/A", "prices": {}})
    entsoe_data = price_data.get("entsoe", {"timestamp": "N/A", "prices": {}})
    tibber_prices = tibber_data.get("prices", {})
    entsoe_prices = entsoe_data.get("prices", {})
    tibber_last_update = tibber_data.get("timestamp", "N/A")
    entsoe_last_update = entsoe_data.get("timestamp", "N/A")
    tomorrow = (current_hour + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_str = tomorrow.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    tibber_tomorrow = "Ja" if tomorrow_str in tibber_prices else "Nee"
    entsoe_tomorrow = "Ja" if tomorrow_str in entsoe_prices else "Nee"
    logger.info(f"Price data: tibber_timestamp={tibber_last_update}, tibber_tomorrow={tibber_tomorrow}, entsoe_timestamp={entsoe_last_update}, entsoe_tomorrow={entsoe_tomorrow}")
    tibber_price = tibber_prices.get(current_hour_str, 0.05)
    entsoe_price = entsoe_prices.get(current_hour_str, 0.05)
    prev_hour = current_hour - timedelta(hours=1)
    next_hour = current_hour + timedelta(hours=1)
    prev_hour_str = prev_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    next_hour_str = next_hour.strftime("%Y-%m-%dT%H:00:00.000+01:00")
    tibber_prev = tibber_prices.get(prev_hour_str, 0.05)
    tibber_next = tibber_prices.get(next_hour_str, 0.05)
    entsoe_prev = entsoe_prices.get(prev_hour_str, 0.05)
    entsoe_next = entsoe_prices.get(next_hour_str, 0.05)
    prev_time = prev_hour.strftime("%a %H:%M")
    current_time = current_hour.strftime("%a %H:%M")
    next_time = next_hour.strftime("%a %H:%M")
    html = """
    <style>
        body {
            background: #0a0a0a;
            color: #00ffcc;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            overflow: hidden;
        }
        h1 {
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 5px;
            color: #ff00ff;
            text-shadow: 0 0 10px #ff00ff, 0 0 20px #00ffcc;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1000px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(0, 255, 204, 0.1);
            border: 2px solid #00ffcc;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 0 15px #00ffcc;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 15px #00ffcc; }
            50% { box-shadow: 0 0 25px #ff00ff; }
            100% { box-shadow: 0 0 15px #00ffcc; }
        }
        .status {
            font-size: 1.2em;
            line-height: 1.5;
            color: #ffcc00;
        }
        .telemetry {
            font-size: 1em;
            line-height: 1.4;
        }
        .slider {
            width: 100%;
            -webkit-appearance: none;
            height: 10px;
            background: #ff00ff;
            outline: none;
            border-radius: 5px;
            box-shadow: 0 0 10px #ff00ff;
        }
        .slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            background: #00ffcc;
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 0 10px #00ffcc;
        }
        .bg-grid {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(#00ffcc33 1px, transparent 1px),
                        linear-gradient(90deg, #00ffcc33 1px, transparent 1px);
            background-size: 20px 20px;
            z-index: -1;
            opacity: 0.3;
            animation: scan 5s linear infinite;
        }
        @keyframes scan {
            0% { background-position: 0 0; }
            100% { background-position: 20px 20px; }
        }
    </style>
    <div class="bg-grid"></div>
    <h1>K.E.E.S. CyberDeck</h1>
    <div class="grid">
        <div class="panel">
            <div class="status">
                <strong>Energy Grid Uplink:</strong><br>
                Tibber - Last Sync: {{tibber_last_update}} | Tomorrow Locked: {{tibber_tomorrow}}<br>
                ENTSO-E - Last Sync: {{entsoe_last_update}} | Tomorrow Locked: {{entsoe_tomorrow}}
            </div>
        </div>
        <div class="panel" id="telemetry">
            <!-- Telemetry goes here -->
        </div>
    </div>
    <script>
        function updateTelemetry() {
            fetch('/data')
                .then(response => response.json())
                .then(data => {
                    let html = '<strong>Heatpump Core:</strong><br>';
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
                            let compressor = huis.compressor_status || 0;
                            let dhw = huis.dhw_heating_status || 0;
                            let dhw_target = huis.dhw_target_temp || 0;
                            let target_temp = huis.target_temp_circuit1 || 0;
                            let overschot = opwek - power;
                            let savings = ((0.25 - price) * (power / 1000)).toFixed(2);
                            html += `
                                <input type="range" class="slider" min="1" max="8" value="${state}" onchange="fetch('/set_state/${huis_id}/${device_name}/'+this.value)"><br>
                                Last Ping: ${data.current_time}<br>
                                Grid Last Hour ({{prev_time}}): ${parseFloat({{tibber_prev}}).toFixed(2)} €/kWh | ${parseFloat({{entsoe_prev}}).toFixed(2)} €/kWh<br>
                                Grid Now ({{current_time}}): ${price.toFixed(2)} €/kWh | ${entsoe_price.toFixed(2)} €/kWh<br>
                                Grid Next ({{next_time}}): ${parseFloat({{tibber_next}}).toFixed(2)} €/kWh | ${parseFloat({{entsoe_next}}).toFixed(2)} €/kWh<br>
                                Power Flux: ${opwek} W | Drain: ${power} W | Net: ${overschot} W<br>
                                Core In: ${temp_in.toFixed(1)}°C | Out: ${temp_out.toFixed(1)}°C<br>
                                Flow Rate: ${flow.toFixed(1)} l/min | External: ${outdoor_temp.toFixed(1)}°C<br>
                                Efficiency: ${cop.toFixed(2)} | Compressor: ${compressor ? "ONLINE" : "OFFLINE"}<br>
                                DHW: ${dhw ? "ACTIVE" : "IDLE"} | Target: ${dhw_target.toFixed(1)}°C<br>
                                Circuit 1 Target: ${target_temp.toFixed(1)}°C<br>
                                Savings: €${savings}/hr (vs 0.25 €/kWh)
                            `;
                        }
                    }
                    document.getElementById('telemetry').innerHTML = html;
                });
        }
        setInterval(updateTelemetry, 5000);
        updateTelemetry();
    </script>
    """.replace("{{tibber_last_update}}", str(tibber_last_update))\
        .replace("{{entsoe_last_update}}", str(entsoe_last_update))\
        .replace("{{tibber_tomorrow}}", tibber_tomorrow)\
        .replace("{{entsoe_tomorrow}}", entsoe_tomorrow)\
        .replace("{{tibber_prev}}", f"{tibber_prev:.2f}")\
        .replace("{{tibber_next}}", f"{tibber_next:.2f}")\
        .replace("{{entsoe_prev}}", f"{entsoe_prev:.2f}")\
        .replace("{{entsoe_next}}", f"{entsoe_next:.2f}")\
        .replace("{{prev_time}}", prev_time)\
        .replace("{{current_time}}", current_time)\
        .replace("{{next_time}}", next_time)
    logger.info("Rendering dashboard HTML")
    return html