# app.py
import sys, yaml, os
from utils.db_handler import DbHandler
from utils.log_handler import LogHandler

job_id = int(sys.argv[1])

env = os.getenv("ENV", "dev")
with open(f"config/{env}.yml") as f:
    config = yaml.safe_load(f)

log_handler = LogHandler(config)
db_handler = DbHandler(config)

class TaskRunner:
    def __init__(self, scheduler_id):
        self.scheduler_id = scheduler_id
        self.task = db_handler.get_schedule(scheduler_id)

    def run(self):
        try:
            db_handler.update_status(self.scheduler_id, "RUN")
            result_file = self.process_query()
            self.send_to_mattermost(result_file)
            self.upload_to_fileserver(result_file)
            db_handler.update_status(self.scheduler_id, "SUCCESS")
            log_handler.log(self.scheduler_id, self.task['scheduler_name'], "DONE", "Task completed")
        except Exception as e:
            db_handler.update_status(self.scheduler_id, "FAIL")
            log_handler.log(self.scheduler_id, self.task['scheduler_name'], "ERROR", str(e))

    def process_query(self):
        import pandas as pd
        cur = db_handler.conn.cursor()
        cur.execute(self.task['query'])
        columns = [col[0] for col in cur.description]
        data = cur.fetchall()
        df = pd.DataFrame(data, columns=columns)
        output_path = f"output/result_{self.scheduler_id}.xlsx"
        df.to_excel(output_path, index=False)
        return output_path

    def send_to_mattermost(self, file_path):
        import requests
        files = {'files': open(file_path, 'rb')}
        data = {'text': f"[{self.scheduler_id}] 실행 완료", 'channel': config['mattermost_channel']}
        requests.post(config['mattermost_url'], files=files, data=data)

    def upload_to_fileserver(self, file_path):
        import requests
        with open(file_path, 'rb') as f:
            requests.post(config['fileserver_url'], files={'file': f})

runner = TaskRunner(job_id)
runner.run()


