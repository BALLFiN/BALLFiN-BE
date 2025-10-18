# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from app.jobs.daily_alarm_job import run_daily_alarm_job

# def start_scheduler():
#     """
#     서버 시작 시 스케줄러를 초기화하고, 
#     매일 오후 16:05(장 마감 이후)에 일봉 기반 알람 계산 작업을 실행함.
#     """
#     scheduler = BackgroundScheduler(timezone="Asia/Seoul")

#     # 매일 오후 16:05에 실행
#     scheduler.add_job(run_daily_alarm_job, 'cron', hour=16, minute=5)

#     scheduler.start()
#     print("✅ 스케줄러 시작됨: 매일 16:05 정배열·기술지표 알람 계산")
from apscheduler.schedulers.background import BackgroundScheduler
from app.jobs.daily_alarm_job import run_daily_alarm_job

def start_scheduler():
    """
    서버 시작 시 스케줄러를 초기화하고, 
    테스트용으로 10초마다 일봉 기반 알람 계산 작업을 실행함.
    (실제 배포 시 cron(hour=16, minute=5)으로 변경)
    """
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")

    # ✅ 테스트용: 10초마다 실행
    scheduler.add_job(run_daily_alarm_job, 'interval', seconds=10)

    scheduler.start()
    print("✅ 스케줄러 시작됨: 10초마다 알람 계산 테스트 중")