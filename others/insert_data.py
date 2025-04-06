from pymongo import MongoClient
from datetime import datetime, timedelta
import random

client = MongoClient("mongodb://localhost:27017/")
db = client["BarbellAI"]

company_collection = db["companies"]
news_collection = db["news"]
disclosure_collection = db["disclosures"]

companies = [
    {"name": "삼성전자", "ticker": "005930"},
    {"name": "SK하이닉스", "ticker": "000660"},
    {"name": "삼성바이오로직스", "ticker": "207940"},
    {"name": "LG에너지솔루션", "ticker": "373220"},
    {"name": "NAVER", "ticker": "035420"},
    {"name": "삼성SDI", "ticker": "006400"},
    {"name": "현대차", "ticker": "005380"},
    {"name": "기아", "ticker": "000270"},
    {"name": "POSCO홀딩스", "ticker": "005490"},
    {"name": "카카오", "ticker": "035720"}
]

# 샘플 텍스트 목록
news_titles = ["신제품 출시", "실적 호조", "글로벌 진출", "AI 기술 도입", "M&A 추진", "노사 협상", "투자 확대", "배당 발표", "주가 상승", "시장 점유율 증가"]
disclosure_titles = ["주요사항보고서", "자기주식취득", "임원변동", "사업보고서", "감사보고서", "주요계약체결", "자회사변동", "공정공시", "증자결정", "주주총회소집"]

# 회사마다 뉴스/공시 10개씩 넣기
for company in companies:
    news_data = []
    disclosure_data = []

    for i in range(10):
        days_ago = random.randint(1, 100)
        sample_date = datetime.now() - timedelta(days=days_ago)

        # 뉴스
        news = {
            "title": f"{company['name']} {random.choice(news_titles)}",
            "content": f"{company['name']} 관련 뉴스 내용 샘플입니다.",
            "company": company["name"],
            "ticker": company["ticker"],
            "date": sample_date
        }
        news_data.append(news)

        # 공시
        disclosure = {
            "title": f"{company['name']} {random.choice(disclosure_titles)}",
            "summary": f"{company['name']} 관련 공시 내용 샘플입니다.",
            "company": company["name"],
            "ticker": company["ticker"],
            "date": sample_date
        }
        disclosure_data.append(disclosure)

    news_collection.insert_many(news_data)
    disclosure_collection.insert_many(disclosure_data)

print("뉴스 및 공시 샘플 데이터 삽입 완료 ✅")
