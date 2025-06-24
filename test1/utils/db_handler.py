import oracledb
from datetime import datetime

class DbHandler:
    def __init__(self, config):
        self.config = config
        self.conn = oracledb.connect(
            user=config['db']['user'],
            password=config['db']['password'],
            dsn=config['db']['dsn'],
            encoding="UTF-8"
        )

    def insert_schedule(self, data):
        sql = """
            INSERT INTO A (scheduler_name, created_by, exec_time, query, status)
            VALUES (:1, :2, :3, :4, 'REGISTERED')
            RETURNING scheduler_id INTO :5
        """
        cur = self.conn.cursor()
        id_var = cur.var(oracledb.NUMBER)
        cur.execute(sql, [
            data['scheduler_name'],
            data['created_by'],
            datetime.fromisoformat(data['exec_time']),
            data['query'],
            id_var
        ])
        self.conn.commit()
        return int(id_var.getvalue())

    def get_schedule(self, scheduler_id):
        sql = "SELECT * FROM A WHERE scheduler_id = :1"
        cur = self.conn.cursor()
        cur.execute(sql, [scheduler_id])
        row = cur.fetchone()
        if row:
            col_names = [d[0].lower() for d in cur.description]
            return dict(zip(col_names, row))
        return None

    def update_status(self, scheduler_id, status):
        sql = "UPDATE A SET status = :1 WHERE scheduler_id = :2"
        cur = self.conn.cursor()
        cur.execute(sql, [status, scheduler_id])
        self.conn.commit()

    def get_logs_for_schedule(self, scheduler_id):
        sql = "SELECT log_time, status, message FROM B WHERE scheduler_id = :1 ORDER BY log_time DESC"
        cur = self.conn.cursor()
        cur.execute(sql, [scheduler_id])
        logs = []
        for row in cur.fetchall():
            logs.append({
                'log_time': row[0].strftime("%Y-%m-%d %H:%M:%S"),
                'status': row[1],
                'message': row[2]
            })
        return logs

    def get_schedules_in_time_range(self, start_time, end_time, status_filter=None):
        sql = "SELECT * FROM A WHERE exec_time BETWEEN :1 AND :2"
        params = [start_time, end_time]
        if status_filter:
            sql += " AND status = :3"
            params.append(status_filter)

        cur = self.conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        col_names = [d[0].lower() for d in cur.description]
        return [dict(zip(col_names, row)) for row in rows]
