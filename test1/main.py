# main.py
from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import os, time, subprocess, sys
from datetime import datetime, timedelta
from utils.db_handler import DbHandler
from utils.log_handler import LogHandler
import yaml

app = Flask(__name__)

# Load config from YML based on ENV
env = os.getenv("ENV", "dev")
with open(f"config/{env}.yml") as f:
    config = yaml.safe_load(f)

log_handler = LogHandler(config)
db_handler = DbHandler(config)
scheduler = BackgroundScheduler()
scheduler.start()

class TaskManagement:
    def __init__(self):
        self.scheduled_jobs = set()

    def launch_app_process(self, job_id):
        try:
            subprocess.Popen([sys.executable, "app.py", str(job_id), env])
            log_handler.log(job_id, None, "STARTED", f"app.py launched for job {job_id}")
        except Exception as e:
            log_handler.log(job_id, None, "ERROR", f"Failed to launch app.py: {str(e)}")
        finally:
            self.scheduled_jobs.remove(job_id)

    def schedule_task(self, job_id, exec_time):
        if job_id in self.scheduled_jobs:
            return
        self.scheduled_jobs.add(job_id)
        scheduler.add_job(
            func=lambda: self.launch_app_process(job_id),
            trigger=DateTrigger(run_date=exec_time),
            id=f"job_{job_id}"
        )
        log_handler.log(job_id, None, "SCHEDULED", f"Scheduled to launch app.py at {exec_time}")

    def add_schedule(self, data):
        job_id = db_handler.insert_schedule(data)
        exec_time = datetime.fromisoformat(data['exec_time'])
        self.schedule_task(job_id, exec_time)
        return job_id

    def kill_task(self, job_id):
        db_handler.update_status(job_id, "KILLED")
        log_handler.log(job_id, None, "KILLED", "Manual kill requested")

    def get_status(self, job_id):
        task = db_handler.get_schedule(job_id)
        if task:
            return {"scheduler_id": job_id, "status": task['status']}
        return {"error": "Not found"}

    def get_logs(self, job_id):
        return db_handler.get_logs_for_schedule(job_id)

    def scan_and_schedule(self):
        now = datetime.now()
        window_start = now - timedelta(seconds=5)
        window_end = now + timedelta(seconds=5)
        tasks = db_handler.get_schedules_in_time_range(window_start, window_end, status_filter='REGISTERED')
        for task in tasks:
            job_id = task['scheduler_id']
            exec_time = task['exec_time']
            self.schedule_task(job_id, exec_time)

mgr = TaskManagement()

scheduler.add_job(mgr.scan_and_schedule, 'interval', seconds=5)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/schedule", methods=["POST"])
def create_schedule():
    data = request.json
    job_id = mgr.add_schedule(data)
    return jsonify({"scheduler_id": job_id})

@app.route("/api/schedule/<int:scheduler_id>/kill", methods=["POST"])
def kill_schedule(scheduler_id):
    mgr.kill_task(scheduler_id)
    return jsonify({"status": "killed"})

@app.route("/api/schedule/<int:scheduler_id>/status", methods=["GET"])
def status_schedule(scheduler_id):
    return jsonify(mgr.get_status(scheduler_id))

@app.route("/api/schedule/<int:scheduler_id>/logs", methods=["GET"])
def get_logs(scheduler_id):
    logs = mgr.get_logs(scheduler_id)
    return jsonify({"logs": logs})

SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

if __name__ == "__main__":
    app.run(port=5000)
