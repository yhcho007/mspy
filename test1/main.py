# main.py
from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import os, subprocess
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
        pass

    def run_task(self, job_id):
        task = db_handler.get_schedule(job_id)
        if task:
            proc = subprocess.Popen(["python", "app.py", str(job_id)])
            db_handler.save_pid(job_id, proc.pid)
            log_handler.log(job_id, task['scheduler_name'], "RUN", f"Started process PID={proc.pid}")
        else:
            log_handler.log(job_id, None, "ERROR", "No such schedule")

    def kill_task(self, job_id):
        pid = db_handler.get_pid(job_id)
        if pid:
            try:
                os.kill(pid, 9)
                db_handler.update_status(job_id, "KILLED")
                log_handler.log(job_id, None, "KILLED", f"Killed process PID={pid}")
            except Exception as e:
                log_handler.log(job_id, None, "ERROR", f"Failed to kill process: {e}")

    def add_schedule(self, data):
        job_id = db_handler.insert_schedule(data)
        trigger = DateTrigger(run_date=data['exec_time'])
        scheduler.add_job(lambda: self.run_task(job_id), trigger=trigger, id=str(job_id))
        return job_id

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

SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

if __name__ == "__main__":
    app.run(port=5000)


