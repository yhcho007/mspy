import oracledb
import traceback
from datetime import datetime

class DbHandler:
    def __init__(self, cfg):
        self.log = None
        self.cfg = cfg

    def get_db_connection(self):
        connection = None
        try:
            connection = oracledb.connect(
                user=self.cfg['user'],
                password=self.cfg['password'],
                dsn=self.cfg['dsn']
            )
        except Exception as e:
            self.log.info(f"get_db_connection error:{traceback.format_exc()}")

        return connection

    def setlog(self,log):
        self.log = log

    def insert_schedule(self, s):
        conn = self.get_db_connection()
        res = None
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO A(SCHEDULER_NAME, CREATED_BY, EXEC_TIME, QUERY, STATUS)
                VALUES (:1, :2, :3, :4, 'REGISTERED')
                RETURNING scheduler_id INTO :id
            """, [s.scheduler_name, s.created_by, s.exec_time, s.query,], id=cur.var(int))
            conn.commit()
            conn.close()
            res = cur.getimplicitresults()[0] if hasattr(cur, 'getimplicitresults') else cur.fetchone()[0]
        except Exception as e:
            self.log.info(f"insert_schedule error:{traceback.format_exc()}")
        return res

    def get_schedule(self, sid):
        conn = self.get_db_connection()
        res = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT SCHEDULER_ID, SCHEDULER_NAME, EXEC_TIME, QUERY, STATUS FROM A WHERE SCHEDULER_ID=:1", [sid])
            row = cur.fetchone()
            if not row: return None
            res = dict(zip([d[0].lower() for d in cur.description], row))
            conn.close()
        except Exception as e:
            self.log.info(f"get_schedule error:{traceback.format_exc()}")
        return res

    def list_schedules(self):
        conn = self.get_db_connection()
        res = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT SCHEDULER_ID, SCHEDULER_NAME, EXEC_TIME, STATUS FROM A")
            cols = [d[0].lower() for d in cur.description]
            res = [dict(zip(cols, row)) for row in cur]
            conn.close()
        except Exception as e:
            self.log.info(f"list_schedules error:{traceback.format_exc()}")
        return res

    def update_status(self, sid, status):
        conn = self.get_db_connection()
        try:
            conn.cursor().execute("UPDATE A SET STATUS=:1 WHERE SCHEDULER_ID=:2", [status, sid])
            conn.commit()
            conn.close()
        except Exception as e:
            self.log.info(f"update_status error:{traceback.format_exc()}")


    def insert_log(self, sid, status, message):
        conn = self.get_db_connection()
        try:
            cur = conn.cursor()
            sql = f"""
                INSERT INTO B(SCHEDULER_ID, SCHEDULER_NAME, STATUS, MESSAGE) 
                VALUES ({sid},
                  (SELECT SCHEDULER_NAME FROM A WHERE SCHEDULER_ID={sid}),
                  '{status}', '{message}')
            """
            # self.log.info(f"insert_log sql: {sql}")
            cur.execute(sql)
            conn.commit()
            conn.close()
        except Exception as e:
            self.log.info(f"insert_log error:{traceback.format_exc()}")

    def fetch_query(self, sql):
        conn = self.get_db_connection()
        res = None
        try:
            if sql:
                cur = conn.cursor()
                cur.execute(sql)
                res = cur.fetchall()
                conn.close()
        except Exception as e:
            self.log.info(f"fetch_query error:{traceback.format_exc()}")
        return res

    def get_schedules_between(self, start, end) :
        sql = f"""
                SELECT SCHEDULER_ID, EXEC_TIME FROM A
                WHERE EXEC_TIME BETWEEN TO_TIMESTAMP('{start}', 'YYYY-MM-DD HH24:MI:SS.FF6')
                                   AND TO_TIMESTAMP('{end}', 'YYYY-MM-DD HH24:MI:SS.FF6')
                AND status = 'REGISTERED'
                """
        conn = self.get_db_connection()
        res = None
        try:
            cur = conn.cursor()
            cur.execute(sql)
            # cur.execute(sql, [start, end])
            rows = cur.fetchall()
            columns = [col[0] for col in cur.description]
            res = [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            self.log.info(f"get_schedules_between error:{traceback.format_exc()}")
        return res


