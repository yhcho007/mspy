import oracledb
from datetime import datetime

class DbHandlerPool:
    def __init__(self, cfg):
        self.pool = oracledb.create_pool(min=1, max=200, **cfg)
        self.log = None

    def setlog(self,log):
        self.log = log

    def insert_schedule(self, s):
        with self.pool.acquire() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO A(SCHEDULER_NAME, CREATED_BY, EXEC_TIME, QUERY, STATUS)
                VALUES (:1, :2, :3, :4, 'REGISTERED')
                RETURNING scheduler_id INTO :id
            """, [s.scheduler_name, s.created_by, s.exec_time, s.query,], id=cur.var(int))
            conn.commit()
            return cur.getimplicitresults()[0] if hasattr(cur, 'getimplicitresults') else cur.fetchone()[0]

    def get_schedule(self, sid):
        with self.pool.acquire() as conn:
            cur = conn.cursor()
            cur.execute("SELECT SCHEDULER_ID, SCHEDULER_NAME, EXEC_TIME, QUERY, STATUS FROM A WHERE SCHEDULER_ID=:1", [sid])
            row = cur.fetchone()
            if not row: return None
            return dict(zip([d[0].lower() for d in cur.description], row))

    def list_schedules(self):
        with self.pool.acquire() as conn:
            cur = conn.cursor()
            cur.execute("SELECT SCHEDULER_ID, SCHEDULER_NAME, EXEC_TIME, STATUS FROM A")
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur]

    def update_status(self, sid, status):
        with self.pool.acquire() as conn:
            conn.cursor().execute("UPDATE A SET STATUS=:1 WHERE SCHEDULER_ID=:2", [status, sid])
            conn.commit()

    def insert_log(self, sid, status, message):
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

    def fetch_query(self, sql):
        with self.pool.acquire() as conn:
            if sql:
                cur = conn.cursor()
                cur.execute(sql)
                return cur.fetchall()
            else:
                return None

    def get_schedules_between(self, start, end) :
        sql = f"""
                SELECT SCHEDULER_ID, EXEC_TIME FROM A
                WHERE EXEC_TIME BETWEEN TO_TIMESTAMP('{start}', 'YYYY-MM-DD HH24:MI:SS.FF6')
                                   AND TO_TIMESTAMP('{end}', 'YYYY-MM-DD HH24:MI:SS.FF6')
                AND status = 'REGISTERED'
                """
        #self.log.info(f"get_schedules_between sql: {sql}")
        reslist = None
        with self.pool.acquire() as conn:
            cur = conn.cursor()
            cur.execute(sql)
            # cur.execute(sql, [start, end])
            rows = cur.fetchall()
            columns = [col[0] for col in cur.description]
            reslist = [dict(zip(columns, row)) for row in rows]
        #self.log.info(f"get_schedules_between reslist: {reslist}")
        return reslist

