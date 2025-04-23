# app/models/chat.py
from pydantic import BaseModel, Field, GetCoreSchemaHandler
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pydantic_core import core_schema

# ✅ MongoDB ObjectId를 FastAPI/Pydantic에서 처리 가능하게 하는 커스텀 타입
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):
        if not ObjectId.is_valid(v):
            raise ValueError('Invalid ObjectId')
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler: GetCoreSchemaHandler):
        return {"type": "string"}

# ✅ 새 대화방 만들 때 (요청)
class ChatSessionCreate(BaseModel):
    title: Optional[str] = None  # 처음엔 제목 없이도 가능

# ✅ 대화방 조회할 때 (응답)
class ChatSessionOut(BaseModel):
    chat_id: str   # MongoDB _id를 chat_id로 매핑
    title: str
    created_at: datetime
    updated_at: datetime
    
class MessageCreate(BaseModel):
    content: str
    model: str  # gpt, gemini 이런거

# ✅ 메시지 조회할 때 (응답)
class MessageOut(BaseModel):
    msg_id: str   
    role: str
    content: str
    ts: datetime

# ✅ 대화방 제목 수정용 Pydantic 모델
class ChatUpdate(BaseModel):
    title: str
