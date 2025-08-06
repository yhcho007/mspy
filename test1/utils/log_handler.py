from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import os

class LogHandler:
    def __init__(self, cfg, sid=None):
        self.log_dir = cfg['log_dir']
        self.log_formatter = cfg['log_format']
        os.makedirs(self.log_dir, exist_ok=True)
        self.logger = logging.getLogger('TaskLogger')  if sid is None else \
            logging.getLogger(f'AppLogger-{sid}')
        self.logger.setLevel(logging.INFO)
        self.log_file_name = f'main_{datetime.now().strftime("%Y%m%d")}.log' if sid is None else \
            f'app_{sid}_{datetime.now().strftime("%Y%m%d")}.log'

        fmt = logging.Formatter(self.log_formatter)

        self.fh = TimedRotatingFileHandler(
            os.path.join(self.log_dir, self.log_file_name),
            when='midnight',
            backupCount=7,
            encoding='utf-8'
        )
        self.fh.setFormatter(fmt)
        self.logger.addHandler(self.fh)
        '''
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        self.logger.addHandler(ch)
        '''

    def info(self, msg):
        self.logger.info(msg)

    def error(self, msg):
        self.logger.error(msg)

    def close(self):
        self.fh.close()
        self.logger.removeHandler(self.fh)
        del self.fh


