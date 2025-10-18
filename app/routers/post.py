from fastapi import APIRouter, Depends, HTTPException
from app.db.mongo import user_collection, news_collection, disclosure_collection
from app.core.security import get_current_user

router = APIRouter(tags=["Post"])

# 🔹 최신순 정렬 공통 함수
def sort_by_date(docs):
    return sorted(docs, key=lambda x: x["date"], reverse=True)

# ✅ 전체 뉴스 + 공시
@router.get("/all")
def get_all_posts(current_user: str = Depends(get_current_user)):
    news = list(news_collection.find({}, {"_id": 0}))
    disclosures = list(disclosure_collection.find({}, {"_id": 0}))
    return sort_by_date(news + disclosures)

# ✅ 뉴스만
@router.get("/news")
def get_news(current_user: str = Depends(get_current_user)):
    news = list(news_collection.find({}, {"_id": 0}))
    return sort_by_date(news)

# ✅ 공시만
@router.get("/disclosures")
def get_disclosures(current_user: str = Depends(get_current_user)):
    disclosures = list(disclosure_collection.find({}, {"_id": 0}))
    return sort_by_date(disclosures)

# ✅ 즐겨찾기 기업 뉴스 + 공시
@router.get("/my-feed")
def get_my_feed(current_user: str = Depends(get_current_user)):
    user = user_collection.find_one({"email": current_user})
    if not user or "favorites" not in user:
        raise HTTPException(404, "즐겨찾기 정보를 찾을 수 없습니다.")

    tickers = user["favorites"]

    news = list(news_collection.find({"ticker": {"$in": tickers}}, {"_id": 0}))
    disclosures = list(disclosure_collection.find({"ticker": {"$in": tickers}}, {"_id": 0}))

    return sort_by_date(news + disclosures)
