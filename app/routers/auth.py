from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.user import UserRegister, UserLogin
from app.db.mongo import user_collection
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token, get_current_user
from datetime import datetime

router = APIRouter()
security = HTTPBearer()

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
        "created_at": datetime.utcnow(),     # ✅ 생성일 추가
        "last_login_at": None                 # ✅ 가입 시 로그인 기록 없음
    })

    return {"message": "회원가입 완료"}


@router.post("/login")
def login(user: UserLogin):
    db_user = user_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(401, "이메일 또는 비밀번호 오류")

    # ✅ 로그인 성공했으면 마지막 로그인 시간 업데이트
    user_collection.update_one(
        {"email": user.email},
        {"$set": {"last_login_at": datetime.utcnow()}}
    )

    token = create_access_token({"sub": user.email})
    return {"access_token": token}

@router.get("/check")
def main(current_user: str = Depends(get_current_user)):
    return {"message": f"어서오세요 {current_user}님!"}

@router.post("/logout")
def logout():
    return {"message": "클라이언트가 토큰을 삭제해야 로그아웃 처리됩니다"}