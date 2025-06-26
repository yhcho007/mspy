import re
import time

import yaml
import traceback
import unicodedata
from pathlib import Path
from openpyxl import Workbook
import oracledb
from utils.log_handler import LogHandler

class TaskRunner:
    def __init__(self, sid, env, db):
        with open(f"config/{env}.yml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        self.output_file_path = Path(cfg['output']['file_path'])
        self.output_file_path.mkdir(parents=True, exist_ok=True)

        self.sid = sid
        self.db = db
        self.log = LogHandler(cfg['log'], self.sid)
        self.db.setlog(self.log)
        self.mm_url = cfg.get('mm_url')
        self.fs_url = cfg.get('fs_url')

    def safe_filename(self, name):
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
        return re.sub(r'[^a-zA-Z0-9_.-]', '_', name)

    def to_clean_sql(self, sqltxt):
        sqltxt = re.sub(r'/\*.*?\*/', '', sqltxt, flags=re.DOTALL)
        sqltxt = re.sub(r'--.*?$', '', sqltxt, flags=re.MULTILINE)
        return sqltxt

    def _get_schedule_record(self, retry=3):
        self.log.info(f"Fetching schedule record for SID: {self.sid}")
        cnt =0
        while True:
            rec = self.db.get_schedule(self.sid)
            if not rec:
                time.sleep(1)
                cnt = cnt + 1
                rec = self.db.get_schedule(self.sid)
                self.log.info(f"No schedule record found for SID {self.sid}. retry {cnt}")
                if cnt > retry:
                    self.log.error(f"No schedule record found for SID {self.sid}. retry {cnt}")
                    break
            else:
                break
        return rec

    def _extract_sql(self, rec):
        if isinstance(rec.get('query'), oracledb.LOB):
            return self.to_clean_sql(rec['query'].read())
        return self.to_clean_sql(rec['query'])

    def _fetch_data(self, sqltxt, retry=3):
        if not sqltxt:
            self.log.info("SQL query is empty or invalid")
            raise ValueError("SQL query is empty or invalid")
        res = self.db.fetch_query(sqltxt)
        self.log.info(f"{self.sid} _fetch_data res:{res}")
        cnt = 0
        while True:
            if not res:
                time.sleep(1)
                cnt = cnt + 1
                res = self.db.fetch_query(sqltxt)
                self.log.info(f"No schedule record found for SID {self.sid}. retry {cnt}")
                if cnt > retry:
                    self.log.error(f"No schedule record found for SID {self.sid}. retry {cnt}")
                    return None
            else:
                return res


    def _save_to_excel(self, rows, file_path):
        try:
            wb = Workbook()
            ws = wb.active
            for r in rows:
                ws.append(r)
            wb.save(file_path)
        except Exception as e:
            self.log.error(f"Failed to save Excel file:\n{traceback.format_exc()}")

    def run(self, retry=3):
        try:
            self.log.info(f"[{self.sid}] Task started.")
            cnt = 0
            while True:
                rec = self._get_schedule_record()
                self.log.info(f"[{self.sid}] rec:{rec}")
                sqltxt = self._extract_sql(rec)
                self.log.info(f"[{self.sid}] sqltxt:{sqltxt}")
                rows = self._fetch_data(sqltxt)
                self.log.info(f"[{self.sid}] rows:{rows}")
                if rows:
                    break
                else:
                    if cnt > retry:
                        msg = f"[{self.sid}] select retry over ERROR"
                        self.log.info(msg)
                        self.db.insert_log(self.sid, "ERROR", msg)
                        self.db.update_status(self.sid, "ERROR")
                        return
                    else:
                        self.log.info(f"[{self.sid}] select retry:{cnt}")
                        cnt = cnt + 1

            safe_name = self.safe_filename(rec['scheduler_name'])
            file_name = f"{safe_name}_{self.sid}.xlsx"
            file_path = self.output_file_path / file_name

            self._save_to_excel(rows, file_path)
            self.log.info(f"[{self.sid}] Task SUCCESS. Saved to {file_path}")
            self.db.update_status(self.sid, "SUCCESS")
            self.db.insert_log(self.sid, "SUCCESS", f"Saved to {file_path}")

            # Optional: File post actions
            # self._post_file(file_path)

            self.log.info(f"[{self.sid}] Task done. File: {file_path}")
            self.db.update_status(self.sid, "DONE")
            self.db.insert_log(self.sid, "DONE", f"[{self.sid}] Task done.")
        except Exception as e:
            err_msg = f"[{self.sid}] Task failed: {e}"
            self.log.error(f"{err_msg}\n{traceback.format_exc()}")
            self.db.insert_log(self.sid, "ERROR", str(e))
            self.db.update_status(self.sid, "ERROR")
        finally:
            self.log.close()


    # Optional future enhancement
    # def _post_file(self, file_path):
    #     files = {'file': open(file_path, 'rb')}
    #     requests.post(self.mm_url, files=files, data={'msg': str(file_path)})
    #     requests.post(self.fs_url, files=files)



'''
if __name__ == "__main__":
    sid, env = int(sys.argv[1]), sys.argv[2]
    TaskRunner(sid, env).run()
'''