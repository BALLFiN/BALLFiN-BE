from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from app.models.alarm import AlarmOut, AlarmSendIn
# ⭐️ 수정된 부분: 컬렉션 변수명을 맞춥니다.
from app.db.mongo import alarm_collection, user_collection
from app.core.security import get_current_user
from bson import ObjectId
from datetime import datetime

router = APIRouter(tags=["Alarm"])

# ✅ 요구사항 1: 알림을 조회하는 API
@router.get("/alarms", response_model=List[AlarmOut],
            summary="사용자 알림 목록 조회",
            description="현재 로그인한 사용자의 모든 알림을 최신순으로 조회합니다.")
def get_user_alarms(limit: int = 100, current_user: str = Depends(get_current_user)):
    user_alarms = list(
        # ⭐️ 수정된 부분
        alarm_collection.find({"user_email": current_user})
        .sort("created_at", -1)
        .limit(limit)
    )
    print(current_user)
    for alarm in user_alarms:
        alarm["_id"] = str(alarm["_id"])
    # MongoDB의 ObjectId를 문자열로 변환하여 반환
    return [AlarmOut(**alarm) for alarm in user_alarms]

# ✅ 요구사항 2: 개별 알림 삭제 API
@router.delete(
    "/alarms/{alarm_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="개별 알림 삭제",
    description="특정 ID를 가진 알림을 삭제합니다. 해당 알림의 소유자만 삭제할 수 있습니다."
)
def delete_alarm(alarm_id: str, current_user: str = Depends(get_current_user)):
    if not ObjectId.is_valid(alarm_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 알림 ID입니다.")

    # ✅ user_email 기준으로 변경
    result = alarm_collection.delete_one(
        {"_id": ObjectId(alarm_id), "user_email": current_user}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="알림을 찾을 수 없거나 삭제 권한이 없습니다."
        )
    return

# ✅ 요구사항 3: 모든 알림 삭제 API
@router.delete("/alarms", status_code=status.HTTP_204_NO_CONTENT,
               summary="모든 알림 삭제",
               description="현재 로그인한 사용자의 모든 알림을 삭제합니다.")
def delete_all_alarms(current_user: str = Depends(get_current_user)):
    alarm_collection.delete_many({"user_email": current_user})
    return


# ✅ 요구사항 4: 특정 관심 기업 사용자들에게 알림 보내기 (관리자용)
@router.post("/alarms/send",
             summary="관심 기업 사용자에게 알림 발송",
             description="특정 기업 코드를 관심 기업으로 등록한 모든 사용자에게 알림을 생성하고 저장합니다.")
def send_alarm_to_users(alarm_in: AlarmSendIn, admin_user: str = Depends(get_current_user)):
    # 실제 운영 환경에서는 관리자 권한을 확인하는 별도의 의존성 주입(dependency)을 사용해야 합니다.
    
    # 해당 기업 코드를 'favorites'에 가진 사용자들을 조회합니다.
    target_users = list(
        user_collection.find({"favorites": alarm_in.company_code}) # ⭐️ 수정된 부분
    )

    if not target_users:
        raise HTTPException(
            status_code=404,
            detail=f"{alarm_in.company_code}를 관심 기업으로 등록한 사용자가 없습니다."
        )

    # 각 사용자에게 보낼 알림 문서를 생성합니다.
    now = datetime.utcnow()
    new_alarms = [
        {
            "user_id": str(user["_id"]),
            "user_email": str(user["email"]),
            "alarm_type": alarm_in.alarm_type,
            "content": alarm_in.content,
            "read": False,
            "created_at": now,
            "target_path": alarm_in.target_path,
            "company": alarm_in.company_code,
            "score": alarm_in.score
        }
        for user in target_users
    ]

    # 생성된 알림들을 DB에 한 번에 저장합니다.
    result = alarm_collection.insert_many(new_alarms) # ⭐️ 수정된 부분
    return {"message": f"{len(result.inserted_ids)}명의 사용자에게 알림을 보냈습니다."}