import oracledb
import traceback
import threading

class DbHandlerPool:
    def __init__(self, cfg):
        self.pool = oracledb.create_pool(min=1, max=200, **cfg)
        self.log = None
        self.local = threading.local()  # 스레드별 데이터 저장소

    def setlog(self, log):
        self.log = log

    # 🔽 스레드별 aaaa 설정/조회 메서드 추가
    def set_aaaa(self, value):
        self.local.aaaa = value

    def get_aaaa(self):
        return getattr(self.local, 'aaaa', None)

    def insert_schedule(self, s):
        res = None
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO A(SCHEDULER_NAME, CREATED_BY, EXEC_TIME, QUERY, STATUS)
                    VALUES (:1, :2, :3, :4, 'REGISTERED')
                    RETURNING scheduler_id INTO :id
                """, [s.scheduler_name, s.created_by, s.exec_time, s.query], id=cur.var(int))
                conn.commit()
                res = cur.getimplicitresults()[0] if hasattr(cur, 'getimplicitresults') else cur.fetchone()[0]
                cur.close()
        except Exception as e:
            self.log.error(f"insert_schedule error:\n{traceback.format_exc()}")
        return res

    def get_schedule(self, sid):
        res = None
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT SCHEDULER_ID, SCHEDULER_NAME, EXEC_TIME, QUERY, STATUS FROM A WHERE SCHEDULER_ID=:1", [sid])
                row = cur.fetchone()
                if row:
                    res = dict(zip([d[0].lower() for d in cur.description], row))
                cur.close()
        except Exception as e:
            self.log.error(f"get_schedule error:\n{traceback.format_exc()}")
        return res

    def list_schedules(self):
        res = None
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute("SELECT SCHEDULER_ID, SCHEDULER_NAME, EXEC_TIME, STATUS FROM A")
                cols = [d[0].lower() for d in cur.description]
                res = [dict(zip(cols, row)) for row in cur]
                cur.close()
        except Exception as e:
            self.log.error(f"list_schedules error:\n{traceback.format_exc()}")
        return res

    def update_status(self, sid, status):
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE A SET STATUS=:1 WHERE SCHEDULER_ID=:2", [status, sid])
                conn.commit()
                cur.close()
        except Exception as e:
            self.log.error(f"update_status error:\n{traceback.format_exc()}")

    def insert_log(self, sid, status, message):
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO B(SCHEDULER_ID, SCHEDULER_NAME, STATUS, MESSAGE) 
                    VALUES (:1,
                        (SELECT SCHEDULER_NAME FROM A WHERE SCHEDULER_ID = :2),
                        :3, :4)
                """, [sid, sid, status, message])
                conn.commit()
                cur.close()
        except Exception as e:
            self.log.error(f"insert_log error:\n{traceback.format_exc()}")

    def fetch_query(self, sql):
        res = None
        try:
            with self.pool.acquire() as conn:
                if sql:
                    cur = conn.cursor()
                    cur.execute(sql)
                    res = cur.fetchall()
                    cur.close()
        except Exception as e:
            self.log.error(f"fetch_query error:\n{traceback.format_exc()}")
        return res

    def get_schedules_between(self, start, end):
        reslist = None
        try:
            sql = f"""
                SELECT SCHEDULER_ID, EXEC_TIME FROM A
                WHERE EXEC_TIME BETWEEN TO_TIMESTAMP('{start}', 'YYYY-MM-DD HH24:MI:SS.FF6')
                                   AND TO_TIMESTAMP('{end}', 'YYYY-MM-DD HH24:MI:SS.FF6')
                  AND status = 'REGISTERED'
            """
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute(sql)
                rows = cur.fetchall()
                columns = [col[0].lower() for col in cur.description]
                reslist = [dict(zip(columns, row)) for row in rows]
                cur.close()
        except Exception as e:
            self.log.error(f"get_schedules_between error:\n{traceback.format_exc()}")
        return reslist
import oracledb
import traceback
import threading

class DbHandlerPool:
    def __init__(self, cfg):
        self.pool = oracledb.create_pool(min=1, max=200, **cfg)
        self.log = None
        self.local = threading.local()  # 스레드별 데이터 저장소

    def setlog(self, log):
        self.log = log

    # 🔽 스레드별 aaaa 설정/조회 메서드 추가
    def set_aaaa(self, value):
        self.local.aaaa = value

    def get_aaaa(self):
        return getattr(self.local, 'aaaa', None)

    def insert_schedule(self, s):
        res = None
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO A(SCHEDULER_NAME, CREATED_BY, EXEC_TIME, QUERY, STATUS)
                    VALUES (:1, :2, :3, :4, 'REGISTERED')
                    RETURNING scheduler_id INTO :id
                """, [s.scheduler_name, s.created_by, s.exec_time, s.query], id=cur.var(int))
                conn.commit()
                res = cur.getimplicitresults()[0] if hasattr(cur, 'getimplicitresults') else cur.fetchone()[0]
                cur.close()
        except Exception as e:
            self.log.error(f"insert_schedule error:\n{traceback.format_exc()}")
        return res

    def get_schedule(self, sid):
        res = None
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT SCHEDULER_ID, SCHEDULER_NAME, EXEC_TIME, QUERY, STATUS FROM A WHERE SCHEDULER_ID=:1", [sid])
                row = cur.fetchone()
                if row:
                    res = dict(zip([d[0].lower() for d in cur.description], row))
                cur.close()
        except Exception as e:
            self.log.error(f"get_schedule error:\n{traceback.format_exc()}")
        return res

    def list_schedules(self):
        res = None
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute("SELECT SCHEDULER_ID, SCHEDULER_NAME, EXEC_TIME, STATUS FROM A")
                cols = [d[0].lower() for d in cur.description]
                res = [dict(zip(cols, row)) for row in cur]
                cur.close()
        except Exception as e:
            self.log.error(f"list_schedules error:\n{traceback.format_exc()}")
        return res

    def update_status(self, sid, status):
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE A SET STATUS=:1 WHERE SCHEDULER_ID=:2", [status, sid])
                conn.commit()
                cur.close()
        except Exception as e:
            self.log.error(f"update_status error:\n{traceback.format_exc()}")

    def insert_log(self, sid, status, message):
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO B(SCHEDULER_ID, SCHEDULER_NAME, STATUS, MESSAGE) 
                    VALUES (:1,
                        (SELECT SCHEDULER_NAME FROM A WHERE SCHEDULER_ID = :2),
                        :3, :4)
                """, [sid, sid, status, message])
                conn.commit()
                cur.close()
        except Exception as e:
            self.log.error(f"insert_log error:\n{traceback.format_exc()}")

    def fetch_query(self, sql):
        res = None
        try:
            with self.pool.acquire() as conn:
                if sql:
                    cur = conn.cursor()
                    cur.execute(sql)
                    res = cur.fetchall()
                    cur.close()
        except Exception as e:
            self.log.error(f"fetch_query error:\n{traceback.format_exc()}")
        return res

    def get_schedules_between(self, start, end):
        reslist = None
        try:
            sql = f"""
                SELECT SCHEDULER_ID, EXEC_TIME FROM A
                WHERE EXEC_TIME BETWEEN TO_TIMESTAMP('{start}', 'YYYY-MM-DD HH24:MI:SS.FF6')
                                   AND TO_TIMESTAMP('{end}', 'YYYY-MM-DD HH24:MI:SS.FF6')
                  AND status = 'REGISTERED'
            """
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute(sql)
                rows = cur.fetchall()
                columns = [col[0].lower() for col in cur.description]
                reslist = [dict(zip(columns, row)) for row in rows]
                cur.close()
        except Exception as e:
            self.log.error(f"get_schedules_between error:\n{traceback.format_exc()}")
        return reslist
