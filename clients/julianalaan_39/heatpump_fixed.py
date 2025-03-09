import json

data = {
    "energy_state_input_holding": 7,
    "opwek": 0.0,
    "price": 0.05,
    "sdm120_watt": 0.0,
    "water_inlet_temp": 0.0,
    "water_outlet_temp": 0.0,
    "current_flow_rate": 0.0,
    "outdoor_air_temp": 0.0,
    "compressor_status": 0,
    "dhw_heating_status": 0,
    "dhw_target_temp": 50.0,
    "target_temp_circuit1": 30.0,
    "cop": 0.0,
    "cop_24h": 0.0,
    "compressor_rpm": 0.0
}

def get_data():
    return data.copy()

def process_data(topic, payload):
    global data
    payload_dict = json.loads(payload)
    
    if "price" in payload_dict:
        data["price"] = float(payload_dict["price"])
    if "opwek" in payload_dict:
        data["opwek"] = float(payload_dict["opwek"])
    if "energy_state_input_holding" in payload_dict:
        data["energy_state_input_holding"] = float(payload_dict["energy_state_input_holding"])
    
    print(f"Processed data: {data}")
    
    if data["price"] < 0.06 and data["opwek"] > 1000:
        data["energy_state_input_holding"] = 5
    elif data["price"] <= 0.15:
        data["energy_state_input_holding"] = 4
    elif data["price"] <= 0.25:
        data["energy_state_input_holding"] = 3
    elif data["price"] <= 0.35:
        data["energy_state_input_holding"] = 2
    else:
        data["energy_state_input_holding"] = 1

def run_heatpump():
    print("Running heatpump logic")
    return data["energy_state_input_holding"]