import os, yaml, sys, psutil, time, threading
import uvicorn
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from concurrent.futures import ThreadPoolExecutor
from utils.db_handler import DbHandler
from utils.log_handler import LogHandler
from typing import List
from app import TaskRunner

# 설정
env = os.getenv("ENV", "dev")
with open(f"config/{env}.yml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
db = DbHandler(cfg['oracle'])
log = LogHandler(cfg['log'])
db.setlog(log)
executor = ThreadPoolExecutor(max_workers=10000)

# FastAPI 앱
app = FastAPI(title="Scheduler API", version="1.0")

# APScheduler
sched = BackgroundScheduler(job_defaults={
    "max_instances" : 100,
    "misfire_grace_time": 60
})
sched.start()

# 데이터 모델
class ScheduleIn(BaseModel):
    scheduler_name: str
    created_by: str
    exec_time: datetime
    query: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/schedule")
def create(s: ScheduleIn):
    sid = db.insert_schedule(s)
    log.info(f"Inserted schedule {sid}")
    sched.add_job(lambda sid=sid: executor.submit(run_task, sid), trigger="date", run_date=s.exec_time, id=str(sid))
    return {"scheduler_id": sid}

@app.get("/schedule/{sid}")
def get_status(sid: int):
    rec = db.get_schedule(sid)
    if not rec:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return rec

@app.delete("/schedule/{sid}")
def delete(sid: int):
    db.update_status(sid, "KILLED")
    try:
        sched.remove_job(str(sid))
    except:
        pass
    log.info(f"Killed schedule {sid}")
    return {"status": "killed"}

@app.get("/schedule", response_model=List[dict])
def list_schedules():
    return db.list_schedules()

# ▶️ 작업 실행 함수 (스레드 기반 실행)
def run_task(sid: int):
    runner = TaskRunner(sid, env, db)
    runner.run()

def run_task_wrapper(sid: int):
    try:
        executor.submit(run_task, sid)
    except Exception as e:
        log.error(f"run_task_wrapper Error {sid}: {traceback.format_exc()}")

# ▶️ 주기적으로 테이블에서 작업을 조회하고 등록
def schedule_scanner():
    while True:
        try:
            now = datetime.now()
            near_future = now + timedelta(seconds=10)

            jobs = db.get_schedules_between(
                now.strftime("%Y-%m-%d %H:%M:%S"),
                near_future.strftime("%Y-%m-%d %H:%M:%S")
            )

            for i, job in enumerate(jobs):
                job_id = str(job["SCHEDULER_ID"])
                if not sched.get_job(job_id):
                    sched.add_job(
                        run_task_wrapper,
                        trigger="date",
                        run_date=job["EXEC_TIME"],
                        id=job_id,
                        args=[job["SCHEDULER_ID"]]
                    )
                    log.info(f"{i} - Scheduled job {job_id} at {job['EXEC_TIME']}")
        except Exception as e:
            log.error(f"schedule_scanner error: {traceback.format_exc()}")
        time.sleep(5)


# ▶️ psutil로 python/uvicorn 프로세스 모니터링
def process_logger():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline_list = proc.info.get('cmdline')
            if not cmdline_list:
                continue
            cmdline = " ".join(cmdline_list)
            if 'python' in cmdline or 'uvicorn' in cmdline:
                print(f"[{proc.info['pid']}] {cmdline}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    '''
    while True:
        print(datetime.now())

        print('---------------------------------------')
        time.sleep(5)
    '''

# ▶️ 백그라운드 스레드 시작
threading.Thread(target=schedule_scanner, daemon=True).start()
threading.Thread(target=process_logger, daemon=True).start()

# ▶️ FastAPI 실행
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
