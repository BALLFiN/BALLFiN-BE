from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, user, post, news, chat, stock, info, alarm, settings
from app.scheduler import start_scheduler
from contextlib import asynccontextmanager

# ✅ lifespan 컨텍스트: 서버 시작/종료 시 실행할 작업 정의
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 서버 시작됨, 스케줄러 등록 중...")
    start_scheduler()  # APScheduler 시작
    yield
    print("🛑 서버 종료됨, 스케줄러 종료")

app = FastAPI(lifespan=lifespan)

# ✅ CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 origin 허용
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 라우터 등록
app.include_router(auth.router, prefix="/api/auth")
app.include_router(user.router, prefix="/api/user")
app.include_router(post.router, prefix="/api/posts")
app.include_router(chat.router, prefix="/api/chat")
app.include_router(news.router, prefix="/api/news")
app.include_router(stock.router, prefix="/api/stock")
app.include_router(info.router, prefix="/api/info")
app.include_router(alarm.router, prefix="/api/alarm")
app.include_router(settings.router, prefix="/api/settings")  # ✅ 추가!
