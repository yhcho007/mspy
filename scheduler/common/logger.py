import logging
import yaml
import datetime

with open("conf.yml") as f:
    config = yaml.safe_load(f)

mgr_log_path = config['log']['mgr_log_path'] + datetime.datetime.now().strftime("%Y%m%d") + ".log"
app_log_path = config['log']['app_log_path'] + datetime.datetime.now().strftime("%Y%m%d") + ".log"
log_format = config['log']['format']

logging.basicConfig(filename=mgr_log_path, level=logging.INFO, format=log_format)
mgr_logger = logging.getLogger("scheduler")

logging.basicConfig(filename=app_log_path, level=logging.INFO, format=log_format)
app_logger = logging.getLogger("app")
