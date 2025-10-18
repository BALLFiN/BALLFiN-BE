from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.user import UserRegister, UserLogin
from app.db.mongo import user_collection
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token, get_current_user
from datetime import datetime

router = APIRouter(tags=["Auth"])
security = HTTPBearer()

# ✅ 기본 알람 설정 (회원가입 알람 시 기본값)
DEFAULT_ALARM_SETTINGS = {
    "price_volatility": False,
    "golden_cross": False,
    "dead_cross": False,
    "macd_golden": False,
    "macd_dead": False,
    "rsi_low": False,
    "rsi_high": False,
    "custom_buy": False,
    "custom_sell": False,
    "news_alert": False
}

@router.post("/register")
def register(user: UserRegister):
    if user_collection.find_one({"email": user.email}):
        raise HTTPException(400, "이미 등록된 이메일입니다.")
    
    hashed_pw = hash_password(user.password)

    user_collection.insert_one({
        "email": user.email,
        "password": hashed_pw,
        "name": user.name,
        "favorites": [],
        "alarm_settings": DEFAULT_ALARM_SETTINGS,  # ✅ 기본 알람 설정 추가
        "created_at": datetime.utcnow(),     # ✅ 생성일 추가
        "last_login_at": None                 # ✅ 가입 시 로그인 기록 없음
    })

    return {"message": "회원가입 완료"}


@router.post("/login")
def login(user: UserLogin):
    db_user = user_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(401, "이메일 또는 비밀번호 오류")
    print(db_user)
    # ✅ 로그인 성공했으면 마지막 로그인 시간 업데이트
    user_collection.update_one(
        {"email": user.email},
        {"$set": {"last_login_at": datetime.utcnow()}}
    )

    token = create_access_token({"sub": user.email})
    return {
        "message": "어서오세요!",
        "access_token": token,  # 토큰은 꼭 포함해서 보내줘야 합니다.
        "user": {
            "_id": str(db_user['_id']),  # ObjectId를 문자열로 변환
            "email": db_user['email'],
            "name": db_user['name'],
            "favorites": db_user['favorites'],
            "alarm_settings": db_user["alarm_settings"],   # ✅ 프론트로 전달
            "created_at": db_user['created_at'].isoformat(),  # datetime을 문자열로 변환
            "last_login_at": db_user['last_login_at'].isoformat() # datetime을 문자열로 변환
        }
    }

@router.get("/check")
def main(current_user: str = Depends(get_current_user)):
    return {"message": f"어서오세요 {current_user}님!"}

@router.post("/logout")
def logout():
    return {"message": "클라이언트가 토큰을 삭제해야 로그아웃 처리됩니다"}