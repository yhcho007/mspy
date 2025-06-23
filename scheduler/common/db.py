import oracledb, yaml
from pathlib import Path
from .logger import logger

conf = yaml.safe_load(open(Path(__file__).parent.parent/"conf.yml"))
ora = conf["oracle"]

class OracleDB:
    def __init__(self):
        self.conn = oracledb.connect(
            user=ora["user"], password=ora["password"], dsn=ora["dsn"]
        )
    def query(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(sql, params or {})
        res = cur.fetchall()
        cur.close()
        return res
    def execute(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(sql, params or {})
        self.conn.commit()
        cur.close()
