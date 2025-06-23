import logging
import yaml

with open("conf.yml") as f:
    config = yaml.safe_load(f)

log_path = config['log']['path']
log_format = config['log']['format']

logging.basicConfig(filename=log_path, level=logging.INFO, format=log_format)
logger = logging.getLogger("scheduler")