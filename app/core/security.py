from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.hash import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

# 환경 변수 또는 기본값
SECRET_KEY = os.getenv("SECRET_KEY", "kwunivnomercyboys")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1

security = HTTPBearer(auto_error=True)

# ✅ 비밀번호 해시화
def hash_password(password: str) -> str:
    return bcrypt.hash(password)

# ✅ 비밀번호 검증
def verify_password(plain_pw: str, hashed_pw: str) -> bool:
    return bcrypt.verify(plain_pw, hashed_pw)

# ✅ JWT 토큰 생성
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ✅ JWT 토큰 디코드 + 유효성 검증 (수동)
def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

# ✅ FastAPI 의존성으로 사용할 토큰 검증기
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False} ) # options={"verify_exp": False} false면 토큰만료 검사 X, true면 O
        user_email = payload.get("sub")
        if user_email is None:
            raise HTTPException(401, "토큰에 사용자 정보 없음")
        return user_email
    except JWTError:
        raise HTTPException(401, "유효하지 않거나 만료된 토큰입니다.")
