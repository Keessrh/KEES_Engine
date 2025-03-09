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
    if "energy_state_input_holding" in payload_dict:
        data["energy_state_input_holding"] = int(payload_dict["energy_state_input_holding"])