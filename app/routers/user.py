from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.user import FavoriteRequest
from app.core.security import get_current_user
from app.db.mongo import user_collection, company_collection
from typing import List, Dict

router = APIRouter(tags=["User"])

@router.get(
    "/companies",
    summary="전체 기업 목록 조회",
    description="등록된 모든 기업 목록을 반환합니다."
)
def get_all_companies(current_user: str = Depends(get_current_user)):
    companies = list(company_collection.find({}, {"_id": 0}))
    return companies


@router.get(
    "/favorites",
    summary="즐겨찾기 목록 조회",
    description="현재 사용자의 즐겨찾기 목록을 반환합니다."
)
def get_favorites(current_user: str = Depends(get_current_user)):
    user = user_collection.find_one({"email": current_user})
    if not user:
        raise HTTPException(404, "사용자 없음")
    return {"favorites": user.get("favorites", [])}


@router.post(
    "/favorites",
    summary="즐겨찾기 추가",
    description="기업명 또는 종목코드로 회사 정보를 검색해 즐겨찾기에 추가합니다."
)
def add_favorite(req: FavoriteRequest, current_user: str = Depends(get_current_user)):
    company = company_collection.find_one({
        "$or": [
            {"stock_code": req.ticker_or_company},
            {"corp_name": req.ticker_or_company}
        ]
    })

    if not company:
        raise HTTPException(404, "일치하는 회사를 찾을 수 없습니다.")

    ticker_to_add = company["stock_code"]

    user = user_collection.find_one({"email": current_user})
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    favorites = user.get("favorites", [])
    if ticker_to_add in favorites:
        return {
            "message": f"{company['corp_name']}({ticker_to_add})은 이미 즐겨찾기에 등록되어 있습니다."
        }

    user_collection.update_one(
        {"email": current_user},
        {"$addToSet": {"favorites": ticker_to_add}}
    )

    return {
        "message": f"{company['corp_name']}({ticker_to_add}) 즐겨찾기 추가 완료!"
    }


@router.delete(
    "/favorites",
    summary="즐겨찾기 제거",
    description="기업명 또는 종목코드로 즐겨찾기 목록에서 제거합니다."
)
def remove_favorite(req: FavoriteRequest, current_user: str = Depends(get_current_user)):
    # company_collection에서 ticker나 corp_name으로 회사 찾기
    company = company_collection.find_one({
        "$or": [
            {"stock_code": req.ticker_or_company},
            {"corp_name": req.ticker_or_company}
        ]
    })

    if not company:
        raise HTTPException(404, "일치하는 회사를 찾을 수 없습니다.")

    ticker_to_remove = company["stock_code"]

    # 즐겨찾기에서 제거
    user_collection.update_one(
        {"email": current_user},
        {"$pull": {"favorites": ticker_to_remove}}
    )

    return {
        "message": f"{company['corp_name']}({ticker_to_remove}) 즐겨찾기 제거 완료!"
    }


@router.get(
    "/companies/search",
    summary="기업 검색",
    description="기업명 또는 종목코드를 기준으로 기업을 검색합니다."
)
def search_companies(
    query: str = Query(..., description="기업명 또는 종목코드로 검색"),
    current_user: str = Depends(get_current_user)
):
    regex_query = {"$regex": query, "$options": "i"}

    search_condition = {
        "$or": [
            {"corp_name": regex_query},
            {"stock_code": regex_query}
        ]
    }

    companies = list(company_collection.find(
        search_condition,
        {"_id": 0, "corp_name": 1, "stock_code": 1}
    ))

    return {"companies": companies}


# {
#   "email": "parkhr0505@gamil.com",
#   "password": "@010505snake"
# }