from fastapi import APIRouter, Query, HTTPException
from pymongo import DESCENDING, ASCENDING, ReturnDocument
from typing import List, Optional
from app.db.mongo import news_collection, user_collection  # 몽고 연결
from datetime import datetime
import math
from datetime import timedelta
from bson import ObjectId

router = APIRouter()

@router.get("/search")
def search_news(
    keyword: Optional[str] = Query(None, description="검색어"),
    impact: Optional[str] = Query(None, description="'positive' 또는 'negative'"),
    sort_by: Optional[str] = Query(None, description="정렬: relevance | newest | oldest | views"),
    start_date: Optional[str] = Query(None, description="시작일자 (예: 2025-05-01)"),
    end_date: Optional[str] = Query(None, description="종료일자 (예: 2025-05-31)"),
    limit: int = 50
):
    query = {}

    # ✅ 텍스트 검색
    projection = {}
    if keyword:
        query["$text"] = {"$search": keyword}
        projection["score"] = {"$meta": "textScore"}

    # ✅ 긍/부정 필터링
    if impact in ["positive", "negative"]:
        query["impact"] = impact

    # ✅ 기간 필터링
    if start_date or end_date:
        query["published_at"] = {}
        try:
            if start_date:
                query["published_at"]["$gte"] = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                end = datetime.strptime(end_date, "%Y-%m-%d")
                query["published_at"]["$lte"] = end + timedelta(days=1) - timedelta(seconds=1)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"날짜 형식 오류: {str(e)}")

    # ✅ 정렬 우선순위: keyword 유무에 따라
    if sort_by == "oldest":
        sort_option = [("published_at", ASCENDING)]
    elif sort_by == "views":
        sort_option = [("views", DESCENDING), ("published_at", DESCENDING)]
    elif sort_by == "relevance" and keyword:
        sort_option = [("score", {"$meta": "textScore"})]
    elif keyword and not sort_by:
        sort_option = [("score", {"$meta": "textScore"})]
    else:
        sort_option = [("published_at", DESCENDING)]  # 기본값

    # ✅ 검색 수행
    cursor = news_collection.find(query, projection).sort(sort_option).limit(limit)

    results = []
    for doc in cursor:
        image_url = doc.get("image_url")
        if isinstance(image_url, float) and math.isnan(image_url):
            image_url = None

        result = {
            "id": str(doc["_id"]),
            "title": doc["title"],
            "published_at": doc["published_at"].strftime("%Y-%m-%d %H:%M"),
            "press": doc["press"],
            "impact": doc["impact"],
            "image_url": image_url,
            "views": doc.get("views", 0),
        }

        # score 있을 경우 포함
        if "score" in doc:
            result["score"] = round(doc["score"], 3)

        results.append(result)

    return {"results": results, "total": len(results)}

@router.get("/my-feed")
def get_user_news_feed(
    user_email: str = Query(..., description="사용자 이메일"),
    limit: int = 20
):
    # ✅ 사용자 즐겨찾기 종목 가져오기
    user = user_collection.find_one({"email": user_email})
    print(user)
    if not user or "favorites" not in user or not user["favorites"]:
        raise HTTPException(status_code=404, detail="즐겨찾기 종목이 없습니다.")

    favorite_tickers = user["favorites"]

    # ✅ 관련 기업 포함된 뉴스 가져오기
    query = {"related_companies": {"$in": favorite_tickers}}
    cursor = news_collection.find(query).sort("published_at", DESCENDING).limit(limit)

    results = []
    for doc in cursor:
        image_url = doc.get("image_url")
        if isinstance(image_url, float) and math.isnan(image_url):
            image_url = None

        results.append({
            "id": str(doc["_id"]),
            "title": doc["title"],
            "published_at": doc["published_at"].strftime("%Y-%m-%d %H:%M"),
            "press": doc["press"],
            "impact": doc["impact"],
            "image_url": image_url,
            "views": doc.get("views", 0),
        })

    return {"results": results, "total": len(results)}

@router.get("/{news_id}")
def get_news_detail(news_id: str):
    try:
        # ✅ 조회수 1 증가시키며 문서 가져오기
        doc = news_collection.find_one_and_update(
            {"_id": ObjectId(news_id)},
            {"$inc": {"views": 1}},
            return_document=ReturnDocument.AFTER
        )
        if not doc:
            raise HTTPException(status_code=404, detail="뉴스를 찾을 수 없습니다.")

        return {
            "id": str(doc["_id"]),
            "title": doc["title"],
            "published_at": doc["published_at"].strftime("%Y-%m-%d %H:%M"),
            "press": doc["press"],
            "impact": doc["impact"],
            "link": doc["link"],
            "image_url": doc.get("image_url"),
            "views": doc.get("views", 0),
            "summary": doc.get("summary"),
            "analysis": doc.get("analysis"),
            "content": doc.get("content"),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"오류 발생: {str(e)}")
