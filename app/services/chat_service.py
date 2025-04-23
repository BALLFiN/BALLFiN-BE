from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
from app.db.mongo import chat_messages
from bson import ObjectId
import google.generativeai as genai

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ✅ Gemini 모델 준비
model = genai.GenerativeModel("gemini-1.5-flash")  # 일반 텍스트 모델

def format_history_to_prompt(history: list, current_question: str) -> str:
    dialogue = ""
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        dialogue += f"{role}: {msg['content']}\n"
    dialogue += f"User: {current_question}"
    return dialogue

# ✅ 일반 호출 (한 번에 전체 답변 받기)
async def ask_llm_gpt(prompt: str) -> str:
    """
    GPT-4o에게 질문(prompt)을 보내고 답변을 받아온다. (스트리밍 ❌)
    """
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 친절한 AI 어시스턴트입니다."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content # 응답온 response에서 content(답변)만 return

async def ask_llm_gemini(prompt: str) -> str:
    """
    Gemini(Pro)에게 질문(prompt)을 보내고 답변을 한 번에 받아온다. (Streaming ❌)
    """
    response = model.start_chat(history=[])  # 대화 히스토리는 현재는 비워둠
    result = response.send_message(prompt)  # ⭐️ 여기 stream=False 기본값
    return result.text

# ✅ 스트리밍 호출 (조각조각 답변 받기)
async def stream_llm_gpt(prompt: str):
    """
    GPT-4o에게 질문(prompt)을 보내고 답변을 스트리밍으로 받는다. (openai>=1.0.0)
    """
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 친절한 AI 어시스턴트입니다."},
            {"role": "user", "content": prompt}
        ],
        stream=True
    )
    return response

async def stream_llm_gemini(prompt: str):
    """
    Gemini(Pro)에게 질문(prompt)을 보내고 답변을 스트리밍으로 받는다.
    """
    response = model.start_chat(history=[])

    # ✅ streaming=True로 스트림 생성
    stream = response.send_message(prompt, stream=True)

    return stream

async def load_chat_history(chat_id: str, limit: int = 10) -> list:
    """
    최근 limit개의 (user/assistant) 메시지를 시간순으로 불러와서 LLM messages 포맷으로 변환
    """
    messages = list(
        chat_messages.find({"chat_id": ObjectId(chat_id)})
        .sort("ts", 1)
        .limit(limit)
    )
    formatted = []
    for m in messages:
        formatted.append({
            "role": m["role"],  # "user" or "assistant"
            "content": m["content"]
        })
    return formatted