from fastapi import APIRouter, Query, HTTPException, Path
from pymongo import DESCENDING, ASCENDING, ReturnDocument
from typing import List, Optional
from app.db.mongo import news_collection, user_collection  # 몽고 연결
from datetime import datetime
import math
from datetime import timedelta
from bson import ObjectId

router = APIRouter()

@router.get(
    "/search",
    summary="뉴스 검색",
    description="""
    검색어, 긍/부정 필터, 날짜 범위, 정렬 옵션 등을 조합하여 뉴스 목록을 검색합니다.

    - keyword: 제목 또는 내용에서 검색어를 포함한 뉴스 검색 (MongoDB 텍스트 인덱스 기반).
    - impact: 뉴스의 긍/부정 라벨을 기준으로 필터링 ('positive' 또는 'negative').
    - start_date / end_date: 뉴스의 게시일 범위를 지정 (YYYY-MM-DD 형식).
    - sort_by: relevance (연관도순), newest (최신순), oldest (오래된순), views (조회수순).
    """
)
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

@router.get(
    "/my-feed",
    summary="사용자 즐겨찾기 기반 뉴스 피드",
    description="""
    사용자의 즐겨찾기 종목을 기준으로 관련 기업이 포함된 뉴스를 조회합니다.

    - 사용자 이메일로 user collection에서 즐겨찾는 종목 목록(`favorites`)을 가져옵니다.
    - 해당 종목이 `related_companies`에 포함된 뉴스만 조회합니다.
    - 최신순으로 정렬됩니다.
    """
    )
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

@router.get(
    "/{news_id}",
    summary="뉴스 상세 조회 및 조회수 증가",
    description="""
    ObjectId 기반으로 특정 뉴스의 상세 정보를 조회하며, 동시에 해당 뉴스의 조회수를 1 증가시킵니다.

    - 뉴스의 전체 정보(제목, 요약, 분석, 본문, 이미지, 링크 등)를 반환합니다.
    - 조회수(`views`)는 호출 시마다 +1 됩니다.
    """
    )
def get_news_detail(
        news_id: str = Path(..., description="조회할 뉴스의 ObjectId (예: 6642e10e8d0b8c9f6f1e7a00)")
    ):
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
