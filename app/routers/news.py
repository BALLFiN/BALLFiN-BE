from fastapi import APIRouter, Query, HTTPException, Path
from pymongo import DESCENDING, ASCENDING, ReturnDocument
from typing import List, Optional
from app.db.mongo import news_collection, user_collection  # 몽고 연결
from app.core.security import get_current_user
from fastapi import Depends
from datetime import datetime
import math
from datetime import timedelta
from bson import ObjectId

router = APIRouter(tags=["News"])

@router.get(
    "/search",
    summary="뉴스 검색",
    description="""
    검색어, 긍/부정/중립 필터, 날짜 범위, 정렬 옵션 등을 조합하여 뉴스 목록을 검색합니다.

    - keyword: 제목 또는 내용에서 검색어를 포함한 뉴스 검색 (MongoDB 텍스트 인덱스 기반).
    - impact: 뉴스의 긍/부정/중립 라벨을 기준으로 필터링 ('positive' | 'negative' | 'neutral').
    - start_date / end_date: 뉴스의 게시일 범위를 지정 (YYYY-MM-DD 형식).
    - sort_by: relevance (연관도순), newest (최신순), oldest (오래된순), views (조회수순).
    - page: 몇 번째 페이지인지 (1부터 시작).
    - limit: 한 페이지당 결과 수.
    """
)
def search_news(
    keyword: Optional[str] = Query(None, description="검색어"),
    impact: Optional[str] = Query(None, description="'positive' | 'negative' | 'neutral'"),
    sort_by: Optional[str] = Query(None, description="정렬: relevance | newest | oldest | views"),
    start_date: Optional[str] = Query(None, description="시작일자 (예: 2025-05-01)"),
    end_date: Optional[str] = Query(None, description="종료일자 (예: 2025-05-31)"),
    page: int = Query(1, description="페이지 번호 (1부터 시작)", ge=1),
    limit: int = Query(10, description="한 페이지당 결과 수", ge=1, le=100)
):
    query = {}

    # ✅ 텍스트 검색
    projection = {}
    if keyword:
        query["$text"] = {"$search": keyword}
        projection["score"] = {"$meta": "textScore"}

    # ✅ 긍/부정/중립 필터링
    if impact in ["positive", "negative", "neutral"]:
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

    # ✅ 정렬 우선순위
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

    # ✅ page → offset 계산
    offset = (page - 1) * limit

    # ✅ 검색 수행 + 페이지네이션 적용
    cursor = news_collection.find(query, projection).sort(sort_option).skip(offset).limit(limit)

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
            "impact_score": doc.get("impact_score", 5),
            "views": doc.get("views", 0),
        }

        if "score" in doc:
            result["score"] = round(doc["score"], 3)

        results.append(result)

    # # ✅ 총 개수도 같이 반환
    # total = news_collection.count_documents(query)
	# ✅ 실제 응답에 담긴 range 계산
    start_idx = offset + 1 if results else 0
    end_idx = offset + len(results)
    return {
        "results": results,
        "page": page,
        "offset": offset,
        "range": f"{start_idx}-{end_idx}",
        "limit": limit
    }

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
    current_user: str = Depends(get_current_user),
    limit: int = 20
):
    # ✅ 사용자 즐겨찾기 종목 가져오기
    user = user_collection.find_one({"email": current_user})
    if not user or "favorites" not in user or not user["favorites"]:
        return {"results": [], "total": 0}

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

@router.get(
    "/by-company/{stock_code}",
    summary="특정 기업 관련 뉴스 목록 조회",
    description="""
    특정 종목 코드(stock_code)가 `related_companies` 필드에 포함된 뉴스 목록을 최신순으로 조회합니다.

    - **stock_code**: 조회할 6자리 종목 코드 (예: "005930").
    - **limit**: 가져올 최신 뉴스의 개수 (기본값: 10).
    """
)
def get_news_by_company(
    stock_code: str = Path(..., description="조회할 종목의 6자리 코드"),
    limit: int = Query(10, description="조회할 최신 뉴스의 개수", ge=1, le=50)
):
    try:
        # ✅ 1. DB에서 조건에 맞는 뉴스 조회
        # related_companies 필드에 stock_code가 포함된 문서를 찾습니다.
        query = {"related_companies": stock_code}
        
        # ✅ 2. 필요한 필드만 선택 (projection)
        projection = {
            "_id": 1,
            "press": 1,
            "title": 1,
            "published_at": 1,
            "impact": 1
        }
        
        # ✅ 3. 최신순으로 정렬하고 개수 제한
        cursor = news_collection.find(query, projection).sort("published_at", DESCENDING).limit(limit)
        
        # ✅ 4. 결과 가공
        results = [
            {
                "id": str(doc["_id"]),
                "press": doc.get("press"),
                "title": doc.get("title"),
                "published_at": doc.get("published_at").strftime("%Y-%m-%d %H:%M") if doc.get("published_at") else None,
                "impact": doc.get("impact")
            } 
            for doc in cursor
        ]

        # 뉴스가 없을 경우 빈 리스트 반환
        if not results:
            return {"message": f"'{stock_code}' 관련 뉴스를 찾을 수 없습니다.", "results": []}

        return {"results": results}

    except Exception as e:
        # 서버 오류 발생 시 500 에러 반환
        raise HTTPException(status_code=500, detail=f"데이터 조회 중 오류 발생: {str(e)}")
