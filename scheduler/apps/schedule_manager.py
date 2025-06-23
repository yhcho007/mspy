from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from apscheduler.schedulers.background import BackgroundScheduler
from typing import List, Dict
import uuid
import threading
import yaml, os
from .app import run_job
from common.db import OracleDB
from common.logger import logger

sched = BackgroundScheduler()
sched.start()
lock = threading.Lock()
app = FastAPI(title="Scheduler API")

class ScheduleIn(BaseModel):
    times: List[str] = Field(..., example=["14:30", "15:45"])
    days_of_month: List[int] = None
    days_of_week: List[int] = None
    params: Dict = {}

class ScheduleOut(ScheduleIn):
    id: str
    owner: str
    status: str  # reserved, running, completed

@app.post("/schedule", response_model=ScheduleOut)
async def create_schedule(s: ScheduleIn, user: str = "user1"):
    sid = str(uuid.uuid4())
    with lock:
        for t in s.times:
            hour, minute = map(int, t.split(":"))
            sched.add_job(
                run_job,
                "cron",
                hour=hour, minute=minute,
                args=[sid, user, s.params],
                id=f"{sid}_{t}"
            )
    db = OracleDB()
    db.execute("INSERT INTO schedules(id, owner, schedule_json, status) VALUES(:i,:u,:j,:s)",
               {"i": sid, "u": user, "j": s.json(), "s": "reserved"})
    return ScheduleOut(id=sid, owner=user, status="reserved", **s.dict())

@app.get("/schedule", response_model=List[ScheduleOut])
async def list_schedules(user: str = "user1", all: bool = False):
    db = OracleDB()
    rows = db.query("SELECT id, owner, schedule_json, status FROM schedules")
    out = []
    for id_, owner, sj, status in rows:
        sch = ScheduleIn(**yaml.safe_load(sj))
        if all or owner == user:
            out.append(ScheduleOut(id=id_, owner=owner, status=status, **sch.dict()))
    return out

@app.put("/schedule/{sid}", response_model=ScheduleOut)
async def update_schedule(sid: str, s: ScheduleIn, user: str = "user1"):
    db = OracleDB()
    rows = db.query("SELECT owner FROM schedules WHERE id = :i", {"i": sid})
    if not rows or rows[0][0] != user:
        raise HTTPException(403)
    sched.remove_job(f"{sid}_*")
    with lock:
        for t in s.times:
            hour, minute = map(int, t.split(":"))
            sched.add_job(run_job, "cron", hour=hour, minute=minute,
                          args=[sid, user, s.params], id=f"{sid}_{t}")
    db.execute("UPDATE schedules SET schedule_json=:j WHERE id=:i",
               {"j": s.json(), "i": sid})
    return ScheduleOut(id=sid, owner=user, status="reserved", **s.dict())

@app.delete("/schedule/{sid}")
async def delete_schedule(sid: str, user: str = "user1"):
    db = OracleDB()
    rows = db.query("SELECT owner FROM schedules WHERE id = :i", {"i": sid})
    if not rows or rows[0][0] != user:
        raise HTTPException(403)
    for job in sched.get_jobs():
        if job.id.startswith(sid):
            job.remove()
    db.execute("DELETE FROM schedules WHERE id = :i", {"i": sid})
    return {"status": "deleted"}

@app.post("/schedule/{sid}/stop")
async def stop_schedule(sid: str, user: str = "user1"):
    db = OracleDB()
    rows = db.query("SELECT owner FROM schedules WHERE id = :i", {"i": sid})
    if not rows or rows[0][0] != user:
        raise HTTPException(403)
    # 중간 stop 기능은 apscheduler에서 job.pause(), but 복잡하여 delete
    for job in sched.get_jobs():
        if job.id.startswith(sid):
            job.remove()
    db.execute("UPDATE schedules SET status='stopped' WHERE id=:i", {"i": sid})
    return {"status": "stopped"}

@app.on_event("shutdown")
def shutdown():
    sched.shutdown()
