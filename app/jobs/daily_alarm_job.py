# app/jobs/daily_alarm_job.py
from datetime import datetime

def run_daily_alarm_job():
    """
    테스트용 작업:
    서버가 켜져 있는 동안 10초마다 자동 실행되며 콘솔에 로그를 찍음.
    (실제 알람 계산 로직은 나중에 여기에 넣으면 됨)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"✅ 스케줄러 동작 중! 현재 시각: {now}")