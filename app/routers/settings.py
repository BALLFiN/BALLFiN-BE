from fastapi import APIRouter, Depends, HTTPException, Path, Body
from app.db.mongo import user_collection
from app.core.security import get_current_user

router = APIRouter(tags=["Settings"], prefix="/api/settings")

# ==============================
# ✅ 전체 알람 설정 조회
# ==============================
@router.get(
    "/alarm",
    summary="알람 설정 조회",
    description="현재 로그인한 사용자의 전체 알람 설정 상태를 조회합니다.",
)
def get_alarm_settings(current_user: str = Depends(get_current_user)):
    user = user_collection.find_one({"email": current_user})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return {"email": current_user, "alarm_settings": user.get("alarm_settings", {})}


# ==============================
# ✅ 개별 알람 설정 토글 (프론트엔드 토글용)
# ==============================
@router.put(
    "/alarm/{alarm_key}",
    summary="단일 알람 토글",
    description="""
    개별 알람을 on/off로 수정합니다.  
    프론트엔드에서 토글 스위치를 바꿀 때 호출하면 됩니다.

    예시:
    ```
    PUT /api/settings/alarm/golden_cross
    {
        "value": true
    }
    ```
    """,
    responses={
        200: {
            "description": "성공적으로 알람 설정이 변경됨",
            "content": {
                "application/json": {
                    "example": {
                        "message": "알람 golden_cross 설정이 true로 변경되었습니다.",
                        "alarm_settings": {
                            "price_volatility": False,
                            "golden_cross": True,
                            "dead_cross": False,
                            "rsi_low": False,
                            "rsi_high": False,
                            "news_alert": False
                        }
                    }
                }
            }
        }
    }
)
def toggle_alarm_setting(
    alarm_key: str = Path(..., description="변경할 알람 키 이름 (예: golden_cross, rsi_high 등)"),
    body: dict = Body(..., example={"value": True}),
    current_user: str = Depends(get_current_user)
):
    """개별 알람 토글"""
    user = user_collection.find_one({"email": current_user})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    alarm_settings = user.get("alarm_settings", {})
    if alarm_key not in alarm_settings:
        raise HTTPException(status_code=400, detail=f"'{alarm_key}'는 유효한 알람 키가 아닙니다.")

    new_value = bool(body.get("value"))
    alarm_settings[alarm_key] = new_value

    user_collection.update_one(
        {"email": current_user},
        {"$set": {"alarm_settings": alarm_settings}}
    )

    return {
        "message": f"알람 {alarm_key} 설정이 {new_value}로 변경되었습니다.",
        "alarm_settings": alarm_settings
    }
