import io, os
import yaml
from common.db import OracleDB
from common.logger import logger
from openpyxl import Workbook
import requests

conf = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "../conf.yml")))
MM_URL = conf["mattermost"]["webhook_url"]

def run_job(job_id: str, user: str, params: dict):
    logger.info(f"Job {job_id} started by {user}")
    db = OracleDB()
    rows = db.query("SELECT * FROM target_table WHERE something = :p", {"p": params["filter"]})
    db.execute("INSERT INTO log_table(job_id, run_time) VALUES(:j, SYSTIMESTAMP)", {"j": job_id})

    wb = Workbook()
    ws = wb.active
    ws.append(["Col1", "Col2", "..."])
    for r in rows:
        ws.append(list(r))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    payload = {"text": f"Job {job_id} completed, by {user}",}
    files = {"file": ("report.xlsx", buf.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = requests.post(MM_URL, data=payload, files=files)
    logger.info(f"Mattermost response: {resp.status_code}")
