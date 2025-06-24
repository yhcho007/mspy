import yaml, os
import requests
import pandas as pd
from utils.db_handler import DbHandler
from utils.log_handler import LogHandler

class TaskRunner:
    def __init__(self, scheduler_id, config=None, db_handler=None, log_handler=None):
        self.scheduler_id = scheduler_id
        self.config = config
        self.db_handler = db_handler
        self.log_handler = log_handler

        if self.config is None:
            env = os.getenv("ENV", "dev")
            with open(f"config/{env}.yml") as f:
                self.config = yaml.safe_load(f)

        if self.db_handler is None:
            self.db_handler = DbHandler(self.config)

        if self.log_handler is None:
            self.log_handler = LogHandler(self.config)

        self.task = self.db_handler.get_schedule(scheduler_id)

    def run(self):
        try:
            result_file = self.process_query()
            self.send_to_mattermost(result_file)
            self.upload_to_fileserver(result_file)
            self.db_handler.update_status(self.scheduler_id, "SUCCESS")
            self.log_handler.log(self.scheduler_id, self.task['scheduler_name'], "DONE", "Task completed")
        except Exception as e:
            self.db_handler.update_status(self.scheduler_id, "FAIL")
            self.log_handler.log(self.scheduler_id, self.task['scheduler_name'], "ERROR", str(e))

    def process_query(self):
        cur = self.db_handler.conn.cursor()
        cur.execute(self.task['query'])
        columns = [col[0] for col in cur.description]
        data = cur.fetchall()
        df = pd.DataFrame(data, columns=columns)
        output_path = f"output/result_{self.scheduler_id}.xlsx"
        df.to_excel(output_path, index=False)
        return output_path

    def send_to_mattermost(self, file_path):
        files = {'files': open(file_path, 'rb')}
        data = {'text': f"[{self.scheduler_id}] 실행 완료", 'channel': self.config['mattermost_channel']}
        requests.post(self.config['mattermost_url'], files=files, data=data)

    def upload_to_fileserver(self, file_path):
        with open(file_path, 'rb') as f:
            requests.post(self.config['fileserver_url'], files={'file': f})