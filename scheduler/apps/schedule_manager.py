import subprocess
import os
import uuid
import oracledb
import psutil
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from croniter import croniter
from common.logger import logger
from common import db


app = FastAPI(title="Oracle Scheduler API")
scheduler = BackgroundScheduler()
scheduler.start()

class ScheduleInput(BaseModel):
    scheduler_name: str
    created_by: str
    cron_expr: str = Field(example="string 예) 분(*:모든or0~59) 시(*:모든or0~23) 일(*:모든or1~31) 월(*:모든or1~12) 요일(*:모든or0:일요일~6:토요일))")
    query: str

class ScheduleDeleteRequest(BaseModel):
    scheduler_ids: List[str]  # 하나 이상 받기
    start_time: Optional[str] = None  # 'YYYY-MM-DD HH24:MI:SS'
    end_time: Optional[str] = None


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
        params = {}
        if created_by:
            conditions.append("created_by = :created_by")
            params['created_by'] = created_by
        if start_time:
            conditions.append("exec_time >= :start_time")
            params['start_time'] = start_time
        if end_time:
            conditions.append("exec_time <= :end_time")
            params['end_time'] = end_time
        if status:
            conditions.append("status = :status")
            params['status'] = status

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM A{where_clause} ORDER BY exec_time"
        cur.execute(sql, params)

        # 컬럼 이름 가져오기
        columns = [col[0].lower() for col in cur.description]

        # 결과를 딕셔너리로 구성하고 LOB 처리
        results = []
        for row in cur.fetchall():
            row_dict = {}
            for col, val in zip(columns, row):
                if isinstance(val, oracledb.LOB):
                    row_dict[col] = val.read()  # CLOB을 문자열로 읽기
                else:
                    row_dict[col] = val
            results.append(row_dict)

        return results

    finally:
        cur.close()
        conn.close()



@app.post("/schedule/kill/{scheduler_id}")
def kill_schedule(scheduler_id: str, user: str):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        # 권한 확인
        cur.execute("SELECT created_by FROM A WHERE scheduler_id = :1", [scheduler_id])
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, detail="Scheduler not found")
        if row[0] != user:
            raise HTTPException(403, detail="Not authorized")

        # 실행 중인 app.py 프로세스 종료
        killed_processes = 0
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmd = proc.info['cmdline']
                if cmd and 'app.py' in cmd and scheduler_id in cmd:
                    proc.kill()
                    killed_processes += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # A 테이블 업데이트
        cur.execute("UPDATE A SET status = 'KILLED' WHERE scheduler_id = :1", [scheduler_id])

        # B 테이블 로그 기록
        cur.execute("""
            INSERT INTO B (log_time, scheduler_id, scheduler_name, status, message)
            VALUES (
                SYSDATE,
                :1,
                (SELECT scheduler_name FROM A WHERE scheduler_id = :1),
                'KILLED',
                :2
            )
        """, [scheduler_id, f'Killed by user {user}, {killed_processes} process(es) terminated'])

        conn.commit()

        return {
            "message": f"Scheduler {scheduler_id} killed.",
            "terminated_processes": killed_processes
        }

    finally:
        cur.close()
        conn.close()


@app.post("/schedule/delete")
def delete_schedules(req: ScheduleDeleteRequest):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        # 기본 조건: status = 'REGISTERED' AND scheduler_id IN (...)
        conditions = ["status = 'REGISTERED'"]
        params = {}

        if req.scheduler_ids:
            conditions.append("scheduler_id IN :scheduler_ids")
            params["scheduler_ids"] = tuple(req.scheduler_ids)

        # 날짜 필터 추가
        if req.start_time:
            try:
                start_dt = datetime.strptime(req.start_time, "%Y-%m-%d %H:%M:%S")
                conditions.append("exec_time >= :start_time")
                params["start_time"] = start_dt
            except ValueError:
                raise HTTPException(400, detail="start_time must be in 'YYYY-MM-DD HH24:MI:SS' format")

        if req.end_time:
            try:
                end_dt = datetime.strptime(req.end_time, "%Y-%m-%d %H:%M:%S")
                conditions.append("exec_time <= :end_time")
                params["end_time"] = end_dt
            except ValueError:
                raise HTTPException(400, detail="end_time must be in 'YYYY-MM-DD HH24:MI:SS' format")

        where_clause = " AND ".join(conditions)
        sql = f"SELECT scheduler_id, exec_time FROM A WHERE {where_clause}"
        cur.execute(sql, params)
        rows = cur.fetchall()

        if not rows:
            raise HTTPException(404, detail="No REGISTERED schedules found for the given conditions")

        # 삭제 대상 exec_time, job_id 리스트
        job_ids = []
        for scheduler_id, exec_time in rows:
            job_id = f"{scheduler_id}_{exec_time.strftime('%Y-%m-%d %H:%M:%S')}"
            job_ids.append(job_id)

        # DB 삭제
        delete_sql = f"DELETE FROM A WHERE {where_clause}"
        cur.execute(delete_sql, params)
        conn.commit()

        # APScheduler 작업 제거
        for job_id in job_ids:
            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                pass  # 이미 제거되었거나 존재하지 않는 job

        return {
            "deleted_count": len(rows),
            "deleted_scheduler_ids": list(set([r[0] for r in rows]))
        }

    finally:
        cur.close()
        conn.close()



