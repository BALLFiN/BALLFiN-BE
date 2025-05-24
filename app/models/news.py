from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class NewsOut(BaseModel):
    news_id: str = Field(..., alias="_id")  # ObjectId를 str로 변환
    link: str
    press: str
    published_at: datetime
    title: str
    image_url: Optional[str] = None
    related_companies: str  # 예: "005930"
    views: int
    summary: str
    impact: str  # "positive" 또는 "negative"
    analysis: str
    content: str

    class Config:
        allow_population_by_field_name = True
