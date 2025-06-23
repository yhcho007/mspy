from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import subprocess
import os
import uuid
from croniter import croniter
from common.logger import logger
from common import db

app = FastAPI(title="Oracle Scheduler API")
scheduler = BackgroundScheduler()
scheduler.start()

class ScheduleInput(BaseModel):
    scheduler_name: str
    created_by: str
    cron_expr: "str 예) 분(*:모든or0~59) 시(*:모든or0~23) 일(*:모든or1~31) 월(*:모드or1~12) 요일(*:모든or0:일요일~6:토요일))"
    query: str

class ScheduleQuery(BaseModel):
    created_by: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading existing scheduled tasks from DB...")
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        now = datetime.now()
        cur.execute("SELECT DISTINCT scheduler_id, exec_time FROM A WHERE status = 'REGISTERED'"
                    " AND exec_time >= TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')")
        rows = cur.fetchall()
        for scheduler_id, exec_time in rows:
            time_str = exec_time.strftime("%Y-%m-%d %H:%M:%S")
            def job(exec_time=exec_time, sid=scheduler_id):
                subprocess.Popen(["python", "apps/app.py", sid, time_str], env=os.environ.copy())

            scheduler.add_job(job, trigger=DateTrigger(run_date=exec_time), id=f"{scheduler_id}_{exec_time}")
    finally:
        cur.close()
        conn.close()

    yield


@app.post("/schedule/register")
def register_schedule(req: ScheduleInput):
    scheduler_id = str(uuid.uuid4())
    now = datetime.now()
    future_times = []
    try:
        iter = croniter(req.cron_expr, now)
        for _ in range(1000):
            next_time = iter.get_next(datetime)
            if (next_time - now).days > 365:
                break
            future_times.append(next_time)
    except Exception as e:
        raise HTTPException(400, detail=f"Invalid cron expression: {str(e)}")

    conn = db.get_connection()
    cur = conn.cursor()
    try:
        for exec_time in future_times:
            cur.execute("""
                INSERT INTO A (scheduler_id, scheduler_name, created_by, exec_time, query, status, created_at)
                VALUES (:1, :2, :3, :4, :5, 'REGISTERED', SYSDATE)
            """, [scheduler_id, req.scheduler_name, req.created_by, exec_time, req.query])

            def job(exec_time=exec_time, sid=scheduler_id):
                subprocess.Popen(["python", "apps/app.py", sid, exec_time.strftime("%Y-%m-%d %H:%M:%S")], env=os.environ.copy())

            if exec_time <= now:
                job()
            else:
                scheduler.add_job(job, trigger=DateTrigger(run_date=exec_time), id=f"{scheduler_id}_{exec_time}")

        conn.commit()
        return {"scheduler_id": scheduler_id, "count": len(future_times)}
    finally:
        cur.close()
        conn.close()

@app.get("/schedule/search")
def search_schedule(
    created_by: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None)
):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        conditions = []
        params = []
        if created_by:
            conditions.append("created_by = :created_by")
            params.append(created_by)
        if start_time:
            conditions.append("exec_time >= :start_time")
            params.append(start_time)
        if end_time:
            conditions.append("exec_time <= :end_time")
            params.append(end_time)
        if status:
            conditions.append("status = :status")
            params.append(status)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM A{where_clause} ORDER BY exec_time"
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

@app.post("/schedule/kill/{scheduler_id}")
def kill_schedule(scheduler_id: str, user: str):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT created_by FROM A WHERE scheduler_id = :1", [scheduler_id])
        row = cur.fetchone()
        if not row or row[0] != user:
            raise HTTPException(403, detail="Not authorized")

        cur.execute("UPDATE A SET status = 'KILLED' WHERE scheduler_id = :1", [scheduler_id])
        cur.execute("INSERT INTO B (log_time, scheduler_id, scheduler_name, status, message) VALUES (SYSDATE, :1, (SELECT scheduler_name FROM A WHERE scheduler_id=:1), 'KILLED', 'Killed by user')", [scheduler_id])
        conn.commit()
        return {"message": "Scheduler killed."}
    finally:
        cur.close()
        conn.close()
