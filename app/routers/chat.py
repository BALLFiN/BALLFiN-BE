# app/routers/chat.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.models.chat import ChatSessionCreate, ChatSessionOut, MessageCreate, MessageOut, ChatUpdate
from app.db.mongo import chat_sessions, chat_messages
from app.core.security import get_current_user
from bson import ObjectId
from datetime import datetime
from fastapi.responses import StreamingResponse
from app.services.chat_service import ask_llm_gpt, stream_llm_gpt, ask_llm_gemini, stream_llm_gemini, load_chat_history, format_history_to_prompt

router = APIRouter()

# ✅ 새 대화방 생성
@router.post("/chats", response_model=ChatSessionOut, 
             summary="새 대화방 생성", description="새로운 대화방(chat session)을 생성하고, 생성된 대화방 정보를 반환합니다.")
def create_chat(session_in: ChatSessionCreate, current_user: str = Depends(get_current_user)):
    now = datetime.utcnow()
    chat_doc = {
        "user_id": current_user,
        "title": session_in.title or "새 대화",
        "created_at": now,
        "updated_at": now
    }
    result = chat_sessions.insert_one(chat_doc)

    # 반환: string 변환
    return ChatSessionOut(
        chat_id=str(result.inserted_id),
        title=chat_doc["title"],
        created_at=chat_doc["created_at"],
        updated_at=chat_doc["updated_at"]
    )

# ✅ 대화방 목록 조회 (최근순)
@router.get("/chats", response_model=List[ChatSessionOut], 
            summary="대화방 목록 조회", description="현재 로그인한 사용자가 생성한 대화방 목록을 최근 업데이트 순으로 조회합니다.")
def list_chats(limit: int = 10, current_user: str = Depends(get_current_user)):
    chats = list(
        chat_sessions.find({"user_id": current_user})
        .sort("updated_at", -1)
        .limit(limit)
    )

    # 반환: list 변환
    return [
        ChatSessionOut(
            chat_id=str(chat["_id"]),
            title=chat["title"],
            created_at=chat["created_at"],
            updated_at=chat["updated_at"]
        )
        for chat in chats
    ]

# ✅ 사용자 질문 추가 + 일반 답변 (Streaming ❌)
@router.post("/chats/{chat_id}/messages")
async def send_message(chat_id: str, msg_in: MessageCreate, current_user: str = Depends(get_current_user)):
    chat = chat_sessions.find_one({"_id": ObjectId(chat_id), "user_id": current_user})
    if not chat:
        raise HTTPException(404, "대화방을 찾을 수 없습니다.")

    now = datetime.utcnow()
    history = await load_chat_history(chat_id, limit=10)
    # ✅ 사용자 질문 저장
    chat_messages.insert_one({
        "chat_id": ObjectId(chat_id),
        "user_id": current_user,
        "role": "user",
        "content": msg_in.content,
        "ts": now
    })

    # ✅ 답변 생성 (한 번에)
    messages = format_history_to_prompt(history, msg_in.content)
    print(messages)
    if msg_in.model == "gpt":
        print("not streaming", msg_in.model)
        response = await ask_llm_gpt(messages)
    else:
        print("not streaming", msg_in.model)
        response = await ask_llm_gemini(messages)
    assistant_content = response

    # ✅ assistant 답변 저장
    chat_messages.insert_one({
        "chat_id": ObjectId(chat_id),
        "user_id": current_user,
        "role": "assistant",
        "content": assistant_content,
        "ts": datetime.utcnow()
    })

    # ✅ 대화방 updated_at 갱신
    chat_sessions.update_one(
        {"_id": ObjectId(chat_id)},
        {"$set": {"updated_at": datetime.utcnow()}}
    )

    # ✅ 완성된 답변 리턴
    return {"assistant": assistant_content}

# ✅ 사용자 질문 추가 + 스트리밍 답변
@router.post("/chats/{chat_id}/messages/stream")
async def stream_message(chat_id: str, msg_in: MessageCreate, current_user: str = Depends(get_current_user)):
    chat = chat_sessions.find_one({"_id": ObjectId(chat_id), "user_id": current_user})
    if not chat:
        raise HTTPException(404, "대화방을 찾을 수 없습니다.")

    now = datetime.utcnow()
    # ✅ 과거 대화 히스토리 불러오기
    history = await load_chat_history(chat_id, limit=10)
    # ✅ 질문 저장
    chat_messages.insert_one({
        "chat_id": ObjectId(chat_id),
        "user_id": current_user,
        "role": "user",
        "content": msg_in.content,
        "ts": now
    })
    
    messages = format_history_to_prompt(history, msg_in.content)
    print(messages)
    async def gpt_response_generator():
        partial_content = ""
        if msg_in.model == "gpt":
            print("streaming", msg_in.model)
            response = await stream_llm_gpt(messages)
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    token = delta.content
                    partial_content += token
                    yield token.encode()
        else:
            print("streaming", msg_in.model)
            response = await stream_llm_gemini(messages)
            for chunk in response:
                if chunk.text:
                    token = chunk.text
                    partial_content += token
                    yield token.encode()

        # 답변 저장
        chat_messages.insert_one({
            "chat_id": ObjectId(chat_id),
            "user_id": current_user,
            "role": "assistant",
            "content": partial_content,
            "ts": datetime.utcnow()
        })

        # 대화방 업데이트
        chat_sessions.update_one(
            {"_id": ObjectId(chat_id)},
            {"$set": {"updated_at": datetime.utcnow()}}
        )

    return StreamingResponse(gpt_response_generator(), media_type="text/event-stream")

# ✅ 특정 대화방 메시지 조회 (시간순)
@router.get("/chats/{chat_id}/messages", response_model=List[MessageOut],
            summary="대화방 메시지 목록 조회", description="특정 대화방(chat_id)에 저장된 모든 메시지를 시간순으로 조회합니다.")
def list_messages(chat_id: str, limit: int = 50, current_user: str = Depends(get_current_user)):
    chat = chat_sessions.find_one({"_id": ObjectId(chat_id), "user_id": current_user})
    if not chat:
        raise HTTPException(404, "대화방을 찾을 수 없습니다.")

    messages = list(
        chat_messages.find({"chat_id": ObjectId(chat_id)})
        .sort("ts", 1)
        .limit(limit)
    )

    # 반환: list 변환
    return [
        MessageOut(
            msg_id=str(message["_id"]),
            role=message["role"],
            content=message["content"],
            ts=message["ts"]
        )
        for message in messages
    ]

# ✅ 대화방 삭제 (대화방 + 메시지 전부)
@router.delete("/chats/{chat_id}",
    			summary="대화방 삭제", description="특정 대화방(chat_id)과 그 대화방에 포함된 모든 메시지를 삭제합니다.")
def delete_chat(chat_id: str, current_user: str = Depends(get_current_user)):
    chat = chat_sessions.find_one({"_id": ObjectId(chat_id), "user_id": current_user})
    if not chat:
        raise HTTPException(404, "대화방을 찾을 수 없습니다.")

    chat_sessions.delete_one({"_id": ObjectId(chat_id)})
    chat_messages.delete_many({"chat_id": ObjectId(chat_id)})

    return {"message": "대화방과 메시지가 삭제되었습니다."}

# ✅ 대화방 제목 수정 API
@router.put("/chats/{chat_id}", summary="대화방 제목 수정", description="특정 대화방(chat_id)의 제목(title)을 수정합니다.")
async def update_chat(chat_id: str, update: ChatUpdate, current_user: str = Depends(get_current_user)):
    chat = chat_sessions.find_one({"_id": ObjectId(chat_id), "user_id": current_user})
    if not chat:
        raise HTTPException(404, "대화방을 찾을 수 없습니다.")

    chat_sessions.update_one(
        {"_id": ObjectId(chat_id)},
        {"$set": {"title": update.title, "updated_at": datetime.utcnow()}}
    )

    return {"message": "대화방 제목이 수정되었습니다."}