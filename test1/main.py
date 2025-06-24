from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import os, time
from datetime import datetime, timedelta
from utils.db_handler import DbHandler
from utils.log_handler import LogHandler
from app import TaskRunner
import yaml
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Load config from YML based on ENV
env = os.getenv("ENV", "dev")
with open(f"config/{env}.yml") as f:
    config = yaml.safe_load(f)

log_handler = LogHandler(config)
db_handler = DbHandler(config)
scheduler = BackgroundScheduler()
scheduler.start()

# 최대 동시 실행 작업 수
executor = ThreadPoolExecutor(max_workers=10000)

# 스케줄러 job_id -> future 참조
running_futures = {}

class TaskManagement:
    def __init__(self):
        pass

    def run_task(self, job_id):
        def task_wrapper():
            task = db_handler.get_schedule(job_id)
            if not task:
                log_handler.log(job_id, None, "ERROR", "No such schedule")
                return

            exec_time = task['exec_time']
            now = datetime.now()
            wait_sec = (exec_time - now).total_seconds()

            if wait_sec > 5:
                delay = wait_sec - 5
                log_handler.log(job_id, task['scheduler_name'], "WAIT", f"Sleeping {delay:.2f} sec before launch")
                time.sleep(delay)

            while datetime.now() < exec_time:
                time.sleep(0.1)

            db_handler.update_status(job_id, "RUN")
            runner = TaskRunner(job_id, config, db_handler, log_handler)
            try:
                runner.run()
            finally:
                running_futures.pop(job_id, None)

        future = executor.submit(task_wrapper)
        running_futures[job_id] = future

    def kill_task(self, job_id):
        future = running_futures.get(job_id)
        if future and not future.done():
            # Python에서는 강제 취소 불가, 상태만 반영
            log_handler.log(job_id, None, "KILLED", "Kill requested - cannot forcibly stop ThreadPoolExecutor task")
        else:
            log_handler.log(job_id, None, "KILLED", "No running task found or already completed")
        db_handler.update_status(job_id, "KILLED")

    def add_schedule(self, data):
        job_id = db_handler.insert_schedule(data)
        trigger = DateTrigger(run_date=datetime.now() + timedelta(seconds=1))
        scheduler.add_job(lambda: self.run_task(job_id), trigger=trigger, id=str(job_id))
        return job_id

    def get_status(self, job_id):
        task = db_handler.get_schedule(job_id)
        if task:
            return {"scheduler_id": job_id, "status": task['status']}
        return {"error": "Not found"}

mgr = TaskManagement()

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

SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

if __name__ == "__main__":
    app.run(port=5000)