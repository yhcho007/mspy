## 🔧스케줄러 예제

Oracle DB, OpenAPI/Swagger, 스케줄링, 강제 종료, Excel 첨부, Mattermost 전송 등 필요한 기능들이 포함되어 있습니다. 비동기 백그라운드 스케줄러로 `apscheduler`를 사용하였습니다.

---

## 📁 스케줄러 디렉토리 구조

```
scheduler/
├── __init__.py
├── conf.yml
├── common/
│   ├── __init__.py
│   ├── db.py
│   └── logger.py
├── apps/
│   ├── __init__.py
│   ├── schedule_manager.py
│   └── app.py
logs/
```

---
## 🔧 스케줄러 실행 방법

1. `pip install fastapi uvicorn apscheduler oracledb openpyxl pyyaml requests`
2. Oracle 테이블 스키마 예시:

```sql
CREATE TABLE schedules(
  id VARCHAR2(50) PRIMARY KEY,
  owner VARCHAR2(50),
  schedule_json CLOB,
  status VARCHAR2(20)
);
CREATE TABLE log_table(
  job_id VARCHAR2(50),
  run_time TIMESTAMP
);
CREATE TABLE target_table(col1 VARCHAR2(100), col2 VARCHAR2(100));
```

3. 메인 실행:

```bash
uvicorn apps.schedule_manager:app --reload
```

Swagger UI에서 스펙 문서 확인 가능 (`http://localhost:8000/docs`).

---
