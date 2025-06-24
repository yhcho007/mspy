# utils/db_handler.py
class DbHandler:
    def __init__(self, config):
        import oracledb
        self.conn = oracledb.connect(user=config['db']['user'],
                                     password=config['db']['password'],
                                     dsn=config['db']['dsn'])

    def get_schedule(self, job_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM A WHERE scheduler_id = :1", [job_id])
        row = cur.fetchone()
        if row:
            return dict(zip([d[0].lower() for d in cur.description], row))
        return None

    def insert_schedule(self, data):
        cur = self.conn.cursor()
        id_var = cur.var(int)
        cur.execute("INSERT INTO A (scheduler_name, created_by, exec_time, query, status) VALUES (:1, :2, :3, :4, 'REGISTERED') RETURNING scheduler_id INTO :5", [
            data['scheduler_name'], data['created_by'], data['exec_time'], data['query'], id_var])
        self.conn.commit()
        return id_var.getvalue()

    def update_status(self, job_id, status):
        cur = self.conn.cursor()
        cur.execute("UPDATE A SET status = :1 WHERE scheduler_id = :2", [status, job_id])
        self.conn.commit()

    def get_pid(self, job_id):
        cur = self.conn.cursor()
        cur.execute("SELECT message FROM B WHERE scheduler_id = :1 AND status = 'RUN' ORDER BY log_time DESC", [job_id])
        row = cur.fetchone()
        if row and "PID=" in row[0]:
            return int(row[0].split("PID=")[-1])
        return None

    def save_pid(self, job_id, pid):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO B (scheduler_id, status, message) VALUES (:1, 'RUN', :2)", [job_id, f"PID={pid}"])
        self.conn.commit()


