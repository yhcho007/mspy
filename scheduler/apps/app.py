import os, sys
import openpyxl
import requests
from common.logger import app_logger
from common import db

WEBHOOK_URL = "https://mattermost.example.com/hooks/your_webhook_id"

if __name__ == "__main__":
    scheduler_id, exec_time = sys.argv[1], sys.argv[2]
    app_logger.info(f"Running {scheduler_id} at {exec_time}")

    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE A SET status = 'START' WHERE scheduler_id = :1 AND TO_CHAR(exec_time, 'YYYY-MM-DD HH24:MI:SS') = :2",
                    [scheduler_id, exec_time])
        conn.commit()

        cur.execute("SELECT query FROM A WHERE scheduler_id = :1 AND TO_CHAR(exec_time, 'YYYY-MM-DD HH24:MI:SS') = :2",
                    [scheduler_id, exec_time])
        row = cur.fetchone()
        if not row:
            raise Exception("No query found")

        query = row[0]
        cur.execute(query)
        data = cur.fetchall()

        wb = openpyxl.Workbook()
        ws = wb.active
        for d in data:
            ws.append(d)
        file_path = f"logs/{scheduler_id}_{exec_time.replace(':', '').replace('-', '').replace(' ', '_')}.xlsx"
        wb.save(file_path)

        # Mattermost 전송
        with open(file_path, 'rb') as f:
            files = {'files': (os.path.basename(file_path), f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            payload = {'text': f"Schedule [{scheduler_id}] executed at {exec_time}"}
            requests.post(WEBHOOK_URL, data=payload, files=files)

        cur.execute("UPDATE A SET status = 'DONE' WHERE scheduler_id = :1 AND TO_CHAR(exec_time, 'YYYY-MM-DD HH24:MI:SS') = :2",
                    [scheduler_id, exec_time])
        cur.execute("INSERT INTO B (log_time, scheduler_id, scheduler_name, status, message) VALUES (SYSDATE, :1, (SELECT scheduler_name FROM A WHERE scheduler_id=:1), 'DONE', 'Success')", [scheduler_id])
        conn.commit()
    except Exception as e:
        app_logger.error(str(e))
        cur.execute("INSERT INTO B (log_time, scheduler_id, scheduler_name, status, message) VALUES (SYSDATE, :1, (SELECT scheduler_name FROM A WHERE scheduler_id = :1), 'ERROR', :2)", [scheduler_id, str(e)])
        conn.commit()
    finally:
        cur.close()
        conn.close()