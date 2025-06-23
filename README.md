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

CREATE TABLE A (
    scheduler_id     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, -- 스케줄 식별자(자동 생성)
    scheduler_name   VARCHAR2(100)   NOT NULL, -- 스케줄 이름 (고객 입력)
    created_by       VARCHAR2(100)   NOT NULL, -- 등록자 ID 또는 이름
    exec_time        TIMESTAMP       NOT NULL, -- 실행 예정 시각
    query            CLOB            NOT NULL, -- 실행할 쿼리 (길이 무제한)
    status           VARCHAR2(20)    NOT NULL, -- 상태 (REGISTERED, DONE, ERROR, KILLED 등)
    created_at       TIMESTAMP       DEFAULT SYSDATE -- 등록 시각
);

COMMENT ON TABLE A IS '스케줄 등록 정보 테이블';
COMMENT ON COLUMN A.scheduler_id IS '스케줄 UUID (자동 생성, 동일 ID로 여러 시간 가능)';
COMMENT ON COLUMN A.scheduler_name IS '스케줄 이름';
COMMENT ON COLUMN A.created_by IS '스케줄 등록자 ID';
COMMENT ON COLUMN A.exec_time IS '실행 예정 시각 (YYYY-MM-DD HH24:MI:SS)';
COMMENT ON COLUMN A.query IS '실행할 SQL 쿼리';
COMMENT ON COLUMN A.status IS '스케줄 상태: REGISTERED, START, DONE, ERROR, KILLED 등';
COMMENT ON COLUMN A.created_at IS '스케줄 등록 시각';
CREATE UNIQUE INDEX a_idx ON A (scheduler_id, exec_time);
COMMIT

CREATE TABLE B (
    log_time         TIMESTAMP       DEFAULT SYSDATE, -- 로그 기록 시각
    scheduler_id     NUMBER    NOT NULL,        -- 스케줄 ID
    scheduler_name   VARCHAR2(100),                   -- 스케줄 이름
    status           VARCHAR2(20),                    -- 상태 (DONE, ERROR, KILLED 등)
    message          VARCHAR2(4000)                   -- 상세 메시지 (오류 메시지, 성공 메시지 등)
);
COMMENT ON TABLE B IS '스케줄 실행 로그 테이블';
COMMENT ON COLUMN B.log_time IS '로그 기록 시각';
COMMENT ON COLUMN B.scheduler_id IS '로그 대상 스케줄 ID';
COMMENT ON COLUMN B.scheduler_name IS '스케줄 이름';
COMMENT ON COLUMN B.status IS '실행 결과 상태';
COMMENT ON COLUMN B.message IS '로그 메시지 (성공/오류 상세)';
COMMIT

DELETE FROM A
SELECT * FROM A WHERE CREATED_AT > SYSDATE ORDER BY CREATED_AT ASC;

SELECT '나는 하나님을 사랑합니다~^^' AS MYWORK, 'GOOD' AS STATUS FROM DUAL

```

3. 메인 실행:

```bash
scheduler 디렉토리에서 다음과 같이 실행한다.
uvicorn apps.schedule_manager:app --reload
```

Swagger UI에서 스펙 문서 확인 가능 (`http://localhost:8000/docs`).

---

4 참고.
루프를 돌면서 insert 하는 SQL 예제
```bash

DECLARE
    v_today DATE := TRUNC(SYSDATE);  -- 오늘 날짜 (시각 제거)
    v_last_ddseq NUMBER;             -- 마지막 DDSEQ 값을 저장할 변수
    v_new_ddseq NUMBER := 0;         -- 새로 생성될 DDSEQ 값
BEGIN
    -- 1. 오늘 날짜에 이미 삽입된 데이터 삭제 (DD가 오늘 날짜인 경우)
    DELETE FROM A
    WHERE DD = TO_CHAR(v_today, 'YYYYMMDD');
    COMMIT;

    -- 2. 오늘 날짜에 마지막 DDSEQ 값을 찾기 (이미 입력된 가장 큰 DDSEQ 값)
    SELECT NVL(MAX(DDSEQ), 0)
    INTO v_last_ddseq
    FROM A
    WHERE DD = TO_CHAR(v_today, 'YYYYMMDD');

    -- 3. 새로 삽입할 DDSEQ 값을 설정 (마지막 DDSEQ 이후부터 10000건 추가)
    v_new_ddseq := v_last_ddseq + 1;

    -- 4. 1000건을 삽입하는 루프 (DD, DT, DDSEQ)
    FOR i IN 1..1000 LOOP
        INSERT INTO A (DD, DT, DDSEQ)
        VALUES (
            TO_CHAR(v_today, 'YYYYMMDD'),  -- 오늘 날짜 (YYYYMMDD 형식)
            TO_CHAR(SYSDATE, 'HH24MISS'), -- 현재 시간 (HH24MISS 형식)
            v_new_ddseq                    -- 새로 생성된 DDSEQ 값
        );
        v_new_ddseq := v_new_ddseq + 1;  -- DDSEQ 값 증가
    END LOOP;

    COMMIT;
END;
/


```


