가장 정밀하고 실용적인 방법은 multiprocessing.Pool을 사용하여, 
실행 직전까지 대기하다가 정각에 subprocess.Popen()을 병렬로 날리는 방식입니다.
이 방식은 1000개 이상의 작업도 OS 한계 내에서 실제로 동시 실행할 수 있는 구조입니다.
ulimit 설정 조정이 필요 합니다.
`oracledb`는 `cx_Oracle`의 공식 후속 패키지이며, Python 3.7+ 이상에서 더 가볍고 설치가 쉬운 구조입니다.

---

## ✅ 전제

* `pip install oracledb`
* Oracle Client 설치 **불필요 (Thin 모드)** unless advanced features needed.
* DB 테이블 A:

  ```sql
  CREATE TABLE A (
      DD     VARCHAR2(8),   -- YYYYMMDD
      DT     VARCHAR2(6),   -- HH24MISS
      DDSEQ  NUMBER
  );
  ```

---

## ✅ `oracledb` 기반 Python 코드 (누락 없이 5초마다 체크, 정확 동시 실행)

```python
import oracledb
import time
from datetime import datetime, timedelta
import multiprocessing
import subprocess
from collections import defaultdict

# Oracle 연결 정보
ORACLE_USER = "your_user"
ORACLE_PASS = "your_pass"
ORACLE_DSN = "localhost/orclpdb"  # Example: host/service_name

# 실행된 DT 기록 (중복 실행 방지)
executed_dts = set()

# Oracle 테이블 A에서 작업 가져오기
def fetch_upcoming_tasks(conn, start_time, end_time):
    cursor = conn.cursor()
    query = """
        SELECT DT, DD, DDSEQ
        FROM A
        WHERE TO_NUMBER(DT) BETWEEN :start_dt AND :end_dt
        ORDER BY DT
    """
    cursor.execute(query, {
        "start_dt": int(start_time.strftime('%H%M%S')),
        "end_dt": int(end_time.strftime('%H%M%S'))
    })

    tasks = []
    for dt, dd, ddseq in cursor:
        if dt not in executed_dts:
            tasks.append({'DT': dt, 'command': ['echo', f'Executing DDSEQ={ddseq}, DT={dt}']})
    return tasks

# 정확한 시각까지 대기 후 동시에 실행
def wait_until_and_execute(task_group):
    dt_str = task_group[0]['DT']
    target_time = datetime.strptime(datetime.now().strftime('%Y%m%d') + dt_str, '%Y%m%d%H%M%S')
    now = datetime.now()
    sleep_sec = (target_time - now).total_seconds()
    if sleep_sec > 0:
        time.sleep(sleep_sec)

    print(f"[{datetime.now()}] Launching {len(task_group)} tasks for DT={dt_str}")
    with multiprocessing.Pool(len(task_group)) as pool:
        pool.map(lambda task: subprocess.Popen(task['command']), task_group)

# DT 기준 그룹화
def group_by_dt(tasks):
    grouped = defaultdict(list)
    for task in tasks:
        grouped[task['DT']].append(task)
    return grouped

def main_loop():
    with oracledb.connect(user=ORACLE_USER, password=ORACLE_PASS, dsn=ORACLE_DSN, mode=oracledb.DEFAULT) as conn:
        while True:
            now = datetime.now()
            # 오버랩 포함해서 누락 방지 (1초 전 ~ 6초 후)
            start_time = now - timedelta(seconds=1)
            end_time = now + timedelta(seconds=6)

            print(f"[{now}] Checking tasks from {start_time.time()} to {end_time.time()}")
            tasks = fetch_upcoming_tasks(conn, start_time, end_time)

            grouped_tasks = group_by_dt(tasks)
            for dt, group in grouped_tasks.items():
                executed_dts.add(dt)
                proc = multiprocessing.Process(target=wait_until_and_execute, args=(group,))
                proc.start()

            time.sleep(5)

if __name__ == '__main__':
    main_loop()
```

---

## ✅ 요점 정리

| 요소                     | 설명                                                 |
| ---------------------- | -------------------------------------------------- |
| **oracledb.connect()** | Oracle에 Thin 모드로 접속                                |
| **DT 누락 방지**           | 매번 1초 오버랩을 줘서 지난 시점도 포함                            |
| **병렬 실행**              | `multiprocessing.Pool`로 **같은 DT 작업 1000개도 동시에 실행** |
| **중복 실행 방지**           | `executed_dts` 세트로 DT 기준 중복 제거                     |

---

## ✅ 추가 팁

* `ORACLE_DSN` 값은 예: `localhost/orclpdb1`, `192.168.1.10/XEPDB1`
* `executed_dts`를 Redis 등 외부로 빼면 다중 서버에서도 충돌 방지 가능
* 각 command를 실제 Python 스크립트로 바꾸면 로직 연동 가능

---

필요하면:

* Oracle에서 실시간 `DT` 데이터 삽입 자동화 코드
* `executed_dts`를 영속 저장하는 방식
* `asyncio` 기반 병렬 실행 (하지만 `Popen` 병렬성은 multiprocessing이 더 효과적)

도 추가로 제공해드릴 수 있습니다.
