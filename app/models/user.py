# app/models/user.py
from pydantic import BaseModel, EmailStr
from typing import List, Optional

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserInDB(BaseModel):
    email: EmailStr
    password: str
    favorites: Optional[List[str]] = []

class FavoriteRequest(BaseModel):
    ticker: str  # 예: "005930"