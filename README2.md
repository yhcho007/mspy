너는 최고의 python 프로그래머야, oracledb, Apscheduler 로 main.py 에서  
Flask를 restapi로 스케줄 등록 테이블 A에 schedule_id 를 key 로 스케줄을 등록(status 값 RESERVED), 
조회, 변경, 삭제, 실행중인 스케줄 app.py를 kill 하고, 스케줄을 exec_time 시간에  app.py기동 한다. 
app.py는 스케줄을 처리하는 모듈로, 기동하여,로그 테이블 스케줄에 status 에 실행(RUN), 
A 테이블 query 처리하고, 결과 엑셀로 저장하고, 메타모스트URL로 메시지와 파일을전송하고, 
파일서버URL로 파일을 전송하며, 성공(SUCCESS)/실패(FAIL), 스케줄 정상종료(DONE)을 저장하고 프로세스를 종료한다. 
Fastapi, swagger를 지원하고, healthcheck API 도 지원해.

스케줄 등록 테이블
CREATE TABLE A (
    scheduler_id     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, -- 스케줄 식별자(자동 생성)
    scheduler_name   VARCHAR2(100)   NOT NULL, -- 스케줄 이름 (고객 입력)
    created_by       VARCHAR2(100)   NOT NULL, -- 등록자 ID 또는 이름
    exec_time        TIMESTAMP       NOT NULL, -- 실행 예정 시각
    query            CLOB            NOT NULL, -- 실행할 쿼리 (길이 무제한)
    status           VARCHAR2(20)    NOT NULL, -- 상태 (REGISTERED, DONE, ERROR, KILLED 등)
    created_at       TIMESTAMP       DEFAULT SYSDATE -- 등록 시각
);

스케줄 처리 로그 테이블
CREATE TABLE B (
    log_time         TIMESTAMP       DEFAULT SYSDATE, -- 로그 기록 시각
    scheduler_id     NUMBER    NOT NULL,        -- 스케줄 ID
    scheduler_name   VARCHAR2(100),                   -- 스케줄 이름
    status           VARCHAR2(20),                    -- 상태 (DONE, ERROR, KILLED 등)
    message          VARCHAR2(4000)                   -- 상세 메시지 (오류 메시지, 성공 메시지 등)
);
oracle DB접속정보, 메타모스트URL, file업로드서버UEL, 로그디렉토리 등은 별도의 yml 파일을 읽어서, 
환경변수로 dev,test,prod 에따라 main.py 와 app.py 에서 읽어 들여 처리하도록 해.

A 테이블에 미래 시간의 exec_time 을 등록하면,
동시에 1000개이상 app.py 프로세스도 exec_time가 동일하면 동시에 기동하고, 또는 exec_time에 기동할수있도록,  
oracledb, Apscheduler SqlAlchemyStore, ThreadPoolExecutor 를 이용해서 거의 완벽한 동시 기동이 가능하도록  코드를 만들어줘.
main.py 는 TaskManagement 클래스로 만들어주고, app.py 는 TaskRunner 클래스로 만들어줘.
로그처리는 1일 단위로 로그파일을 만들고, 로그처리 함수는 LogHandler 클래서에서,
DB 처리는 DbHandler 클래스에서 하도록 만들어줘.
