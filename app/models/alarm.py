from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AlarmSendIn(BaseModel):
    # 기존 필드는 동일
    company_code: str = Field(..., description="알람을 보낼 대상 관심 기업 코드")
    alarm_type: str = Field(..., description="알람 종류")
    content: str = Field(..., description="알람 내용")
    target_path: str = Field(..., description="알림 클릭 시 이동할 경로")
    score: Optional[int] = Field(None, description="관련 점수 (선택 사항)")

    class Config:
        schema_extra = {
            "example": {
                "company_code": "005930",
                "alarm_type": "긴급 뉴스",
                "content": "삼성전자, 새로운 AI 칩 공개!",
                "target_path": "/stocks/005930/news/45",
                "score": 85
            }
        }

class AlarmOut(BaseModel):
    # 기존 필드는 동일
    alarm_id: str = Field(alias="_id")
    user_id: str
    alarm_type: str
    content: str
    read: bool = False
    target_path: Optional[str] = None
    created_at: datetime
    company: Optional[str] = None
    score: Optional[int] = None

    class Config:
        allow_population_by_field_name = True
        # ... (json_encoders, schema_extra 등)