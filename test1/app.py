import oracledb
import yaml, sys, os, time
from utils.db_handler import DbHandler
from utils.log_handler import LogHandler
import openpyxl, requests
import unicodedata
import re
import traceback

class TaskRunner:
    def __init__(self, sid, env, db):
        with open(f"config/{env}.yml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.output_file_path = cfg['output']['file_path']
        os.makedirs(self.output_file_path, exist_ok=True)
        self.sid = sid
        self.db = db
        self.log = LogHandler(cfg['log'], self.sid)
        self.mm_url = cfg['mm_url']
        self.fs_url = cfg['fs_url']

    def safe_filename(self, name):
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
        name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
        return name

    def to_clean_sql(self, sqltxt):
        sqltxt = re.sub(r'/\*.*?\*/','',sqltxt, flags=re.DOTALL)
        sqltxt = re.sub(r'--.*?\*$', '', sqltxt, flags=re.MULTILINE)
        return sqltxt


    def run(self):
        try:
            self.db.update_status(self.sid, "RUN")
            self.log.info(f"App {self.sid} --1--")
            self.db.insert_log(self.sid, "RUN", f"RUN {self.sid}")
            self.log.info(f"App {self.sid} --2--")
            rec = self.db.get_schedule(self.sid)
            self.log.info(f"App {self.sid} --2.5-- rec:{rec}")
            sqltxt = None
            if isinstance(rec['query'], oracledb.LOB):
                sqltxt = self.to_clean_sql(rec['query'].read()) if rec['query'] is not None else None
            self.log.info(f"App {self.sid} --3-- QUERY:{sqltxt}")
            rows = self.db.fetch_query(sqltxt)
            self.log.info(f"App {self.sid} --4--")
            safe_name = self.safe_filename(rec['scheduler_name'])
            path = f"{safe_name}_{self.sid}.xlsx"
            file_path = os.path.join(self.output_file_path, path)
            self.log.info(f"App {self.sid} --5-- file_path:{file_path}")
            wb = openpyxl.Workbook()
            ws = wb.active
            for r in rows:
                ws.append(r)
            wb.save(file_path)
            self.log.info(f"App {self.sid} --6--")
            files = {'file': open(file_path, 'rb')}
            requests.post(self.mm_url, files=files, data={'msg': file_path})
            requests.post(self.fs_url, files=files)
            self.log.info(f"App {self.sid} --7--")
            self.db.insert_log(self.sid, "SUCCESS", f"Saved to {file_path}")
            self.db.update_status(self.sid, "DONE")
            self.log.info(f"Task {self.sid} DONE")
            self.log.info(f"App {self.sid} --8--")
            return
        except Exception as e:
            self.db.insert_log(self.sid, "ERROR", str(e))
            self.log.error(f"Task {self.sid}  failed: {traceback.format_exc()}")

        self.db.update_status(self.sid, "ERROR")



'''
if __name__ == "__main__":
    sid, env = int(sys.argv[1]), sys.argv[2]
    TaskRunner(sid, env).run()
'''