# app/routers/user.py

from fastapi import APIRouter, Depends, HTTPException
from app.models.user import FavoriteRequest
from app.core.security import get_current_user
from app.db.mongo import user_collection, company_collection

router = APIRouter()

@router.get("/companies")
def get_all_companies(current_user: str = Depends(get_current_user)):
    companies = list(company_collection.find({}, {"_id": 0}))
    return companies

# ⭐ 즐겨찾기 목록 조회
@router.get("/favorites")
def get_favorites(current_user: str = Depends(get_current_user)):
    user = user_collection.find_one({"email": current_user})
    if not user:
        raise HTTPException(404, "사용자 없음")
    return {"favorites": user.get("favorites", [])}

# ⭐ 즐겨찾기 추가
@router.post("/favorites")
def add_favorite(req: FavoriteRequest, current_user: str = Depends(get_current_user)):
    user_collection.update_one(
        {"email": current_user},
        {"$addToSet": {"favorites": req.ticker}}  # 중복 없이 추가
    )
    return {"message": "즐겨찾기 추가 완료"}

# ⭐ 즐겨찾기 제거
@router.delete("/favorites")
def remove_favorite(req: FavoriteRequest, current_user: str = Depends(get_current_user)):
    user_collection.update_one(
        {"email": current_user},
        {"$pull": {"favorites": req.ticker}}
    )
    return {"message": "즐겨찾기 제거 완료"}
