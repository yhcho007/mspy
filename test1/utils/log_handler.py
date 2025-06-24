# utils/log_handler.py
import logging
import os
from datetime import datetime

class LogHandler:
    def __init__(self, config):
        log_dir = config['log_dir']
        os.makedirs(log_dir, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        self.logger = logging.getLogger("scheduler")
        handler = logging.FileHandler(os.path.join(log_dir, f"{today}.log"))
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log(self, job_id, job_name, status, msg):
        self.logger.info(f"[{job_id}] {job_name or ''} - {status}: {msg}")
