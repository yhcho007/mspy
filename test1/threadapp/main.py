import os, yaml, psutil, time, threading, traceback
import uvicorn
import gc
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from concurrent.futures import ThreadPoolExecutor
from typing import List
from utils.db_handler_pool import DbHandlerPool
from utils.log_handler import LogHandler
from threadapp.app import TaskRunner

# 설정
env = os.getenv("ENV", "dev")
with open(f"config/{env}.yml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
db = DbHandlerPool(cfg['oracle'])
log = LogHandler(cfg['log'])
db.setlog(log)

# FastAPI 앱
app = FastAPI(
    title="Scheduler API",
    description="An API for managing and executing scheduled database queries.",
    version="1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

class ScheduleIn(BaseModel):
    scheduler_name: str
    created_by: str
    exec_time: datetime
    query: str

    class Config:
        json_schema_extra = {
            "example": {
                "scheduler_name": "DailyReport",
                "created_by": "admin",
                "exec_time": "2025-06-26T15:00:00",
                "query": "SELECT * FROM report_table"
            }
        }

class TaskManager:
    def __init__(self, max_workers=1000):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()
        self.active_tasks = set()
        self.completed_tasks = 0
        self.sched = None
        threading.Thread(target=self._monitor_threads, daemon=True).start()
        threading.Thread(target=self._schedule_scanner, daemon=True).start()
        #threading.Thread(target=self._process_logger, daemon=True).start()

    def run_task(self, sid: int):
        runner = TaskRunner(sid, env, db)
        try:
            runner.run()
        except Exception as e:
            log.error(f"Task {sid} failed: {traceback.format_exc()}")
        finally:
            with self.lock:
                self.completed_tasks += 1
                self.active_tasks.discard(threading.current_thread())

    def run_task_wrapper(self, sid: int):
        try:
            t = threading.Thread(target=self.run_task, args=(sid,))
            with self.lock:
                self.active_tasks.add(t)
            t.start()
        except Exception as e:
            log.error(f"run_task_wrapper Error {sid}: {traceback.format_exc()}")

    def _monitor_threads(self):
        while True:
            with self.lock:
                job_count = 0
                if self.sched:
                    job_count = len(self.sched.get_jobs())
                print(f"[{datetime.now()}]JobCount:{job_count} Active: {len(self.active_tasks)} | Completed: {self.completed_tasks}")
                if len(self.active_tasks) == 0:
                    self.completed_tasks = 0
            time.sleep(2)

    def _schedule_scanner(self):
        self.sched = BackgroundScheduler(job_defaults={"max_instances": 100, "misfire_grace_time": 60})
        self.sched.start()
        while True:
            try:
                now = datetime.now()
                near_future = now + timedelta(seconds=15)
                jobs = db.get_schedules_between(
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                    near_future.strftime("%Y-%m-%d %H:%M:%S")
                )
                for i, job in enumerate(jobs):
                    job_id = str(job["SCHEDULER_ID"])
                    if not self.sched.get_job(job_id):
                        self.sched.add_job(
                            self.run_task_wrapper,
                            trigger="date",
                            run_date=job["EXEC_TIME"],
                            id=job_id,
                            args=[job["SCHEDULER_ID"]]
                        )
                        db.update_status(job_id, "RUNNING")
                        db.insert_log(job_id, "RUNNING", f"RUNNING {job_id}")
                        log.info(f"{i} - Scheduled job {job_id} at {job['EXEC_TIME']}")
            except Exception as e:
                log.error(f"schedule_scanner error: {traceback.format_exc()}")
            time.sleep(10)

    def _process_logger(self):
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

# 싱글톤 인스턴스 생성
task_manager = TaskManager()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/schedule")
def create(s: ScheduleIn):
    sid = db.insert_schedule(s)
    log.info(f"Inserted schedule {sid}")
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
    log.info(f"Killed schedule {sid}")
    return {"status": "killed"}

@app.get("/schedule", response_model=List[dict])
def list_schedules():
    return db.list_schedules()

if __name__ == "__main__":
    uvicorn.run("threadapp.main:app", host="0.0.0.0", port=8000, reload=True)
