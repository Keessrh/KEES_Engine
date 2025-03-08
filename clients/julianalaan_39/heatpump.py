import logging

logging.basicConfig(filename="/root/new_main.log", level=logging.DEBUG, 
                    format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

def run_heatpump():
    logger.info("Heatpump stub running for julianalaan_39—ready for Modbus!")
