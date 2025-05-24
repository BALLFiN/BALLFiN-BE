from pymongo import MongoClient
from datetime import datetime, timedelta
import random
import pandas as pd
from pymongo import TEXT

client = MongoClient("mongodb+srv://hrpark:Y3LplbJpL8hr3W1y@hrpark.h6uhx.mongodb.net/?retryWrites=true&w=majority&appName=hrpark")
db = client["BarbellAI"]

collection = db["news"]

## 텍스트 인덱스 생성 (제목, 본문 대상)
# collection.create_index(
#     [("title", TEXT), ("content", TEXT)],
#     default_language="none"  # 한국어 설정 (MongoDB는 영어 기반이 기본)
# )

# # CSV 불러오기
# df = pd.read_csv("/Users/phr/Downloads/삼성전자.csv")
# df = df.head(500)

# # ✅ 필요한 전처리 함수
# def parse_datetime(korean_time_str):
#     return datetime.strptime(korean_time_str, "%Y년 %m월 %d일 %H:%M")

# companies = [
#     {"name": "삼성전자", "ticker": "005930"},
#     {"name": "SK하이닉스", "ticker": "000660"},
#     {"name": "삼성바이오로직스", "ticker": "207940"},
#     {"name": "LG에너지솔루션", "ticker": "373220"},
#     {"name": "NAVER", "ticker": "035420"},
#     {"name": "삼성SDI", "ticker": "006400"},
#     {"name": "현대차", "ticker": "005380"},
#     {"name": "기아", "ticker": "000270"},
#     {"name": "POSCO홀딩스", "ticker": "005490"},
#     {"name": "카카오", "ticker": "035720"}
# ]

# # ✅ 변환 및 삽입
# documents = []
# for _, row in df.iterrows():
#     doc = {
#         "link": row["link_url"],
#         "press": row["agency"],
#         "published_at": parse_datetime(row["date"]),
#         "title": row["title"],
#         "image_url": row.get("image_url"),
#         "related_companies": "005930",
#         "views": 0,
#         "summary": "summary 입니다.",
#         "impact": "positive",  # 'positive' 또는 'negative'
#         "analysis": "상세분석입니다.",
#         "content": row['content']
#     }
#     documents.append(doc)
    
# print(documents[0])

# collection.insert_many(documents)
# print("✅ 뉴스 데이터 삽입 완료")