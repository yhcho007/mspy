import oracledb
import traceback

class DbHandlerPool:
    def __init__(self, cfg):
        self.pool = oracledb.create_pool(min=1, max=200, **cfg)
        self.log = None

    def setlog(self,log):
        self.log = log

    def insert_schedule(self, s):
        res = None
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO A(SCHEDULER_NAME, CREATED_BY, EXEC_TIME, QUERY, STATUS)
                    VALUES (:1, :2, :3, :4, 'REGISTERED')
                    RETURNING scheduler_id INTO :id
                """, [s.scheduler_name, s.created_by, s.exec_time, s.query, ], id=cur.var(int))
                conn.commit()
                res = cur.getimplicitresults()[0] if hasattr(cur, 'getimplicitresults') else cur.fetchone()[0]
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
                if not row: return None
                res = dict(zip([d[0].lower() for d in cur.description], row))
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
        except Exception as e:
            self.log.error(f"list_schedules error:\n{traceback.format_exc()}")
        return res


    def update_status(self, sid, status):
        try:
            with self.pool.acquire() as conn:
                conn.cursor().execute("UPDATE A SET STATUS=:1 WHERE SCHEDULER_ID=:2", [status, sid])
                conn.commit()
        except Exception as e:
            self.log.error(f"update_status error:\n{traceback.format_exc()}")


    def insert_log(self, sid, status, message):
        try:
            with self.pool.acquire() as conn:
                cur = conn.cursor()
                sql = f"""
                    INSERT INTO B(SCHEDULER_ID, SCHEDULER_NAME, STATUS, MESSAGE) 
                    VALUES ({sid},
                      (SELECT SCHEDULER_NAME FROM A WHERE SCHEDULER_ID={sid}),
                      '{status}', '{message}')
                """
                self.log.info(f"insert_log sql: {sql}")
                cur.execute(sql)
                conn.commit()
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
                else:
                    res = None
        except Exception as e:
            self.log.error(f"fetch_query error:\n{traceback.format_exc()}")


    def get_schedules_between(self, start, end) :
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
                # cur.execute(sql, [start, end])
                rows = cur.fetchall()
                columns = [col[0] for col in cur.description]
                reslist = [dict(zip(columns, row)) for row in rows]
            # self.log.info(f"get_schedules_between reslist: {reslist}")
        except Exception as e:
            self.log.error(f"get_schedules_between error:\n{traceback.format_exc()}")

        return reslist

