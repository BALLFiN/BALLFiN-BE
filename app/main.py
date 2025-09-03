from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, user, post, news, chat, stock, info


app = FastAPI()

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