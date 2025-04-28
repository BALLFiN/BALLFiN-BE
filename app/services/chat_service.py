from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
from app.db.mongo import chat_messages
from bson import ObjectId
import google.generativeai as genai
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from app.models.llm.graph import create_agent

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ✅ Gemini 모델 준비
model = genai.GenerativeModel("gemini-1.5-flash")  # 일반 텍스트 모델

# langchain 래퍼 모델로 사용해야 랭그래프와 호환 가능함
gpt = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0
    )
gemini = ChatGoogleGenerativeAI(
    model = "gemini-1.5-flash",
    temperature=0,
    api_key=os.getenv("GOOGLE_API_KEY")
)
gpt_agent = create_agent(gpt)
gemini_agent = create_agent(gemini)

print("✅ gpt, Gemini 에이전트 준비 완료")



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
    print("ask to gpt")
    try:
        response = await gpt_agent.ainvoke(
            {"messages": [
                {"role": "user",
                "content": prompt}
                ]
                }
                )
        return response['messages'][-1].content
    
    except Exception as e:
        print(f"[ERROR] Gpt 응답 실패: {e}")
        return f"[오류] Gpt 응답 실패: {str(e)}"

async def ask_llm_gemini(prompt: str) -> str:
    """
    Gemini(Pro)에게 질문(prompt)을 보내고 답변을 한 번에 받아온다. (Streaming ❌)
    """
    print("ask to gemini")
    try:
        response = gemini_agent.invoke(
            {"messages": [
                {"role": "user",
                "content": prompt}
                ]
                }
                )
        return response['messages'][-1].content
    
    except Exception as e:
        print(f"[ERROR] Gemini 응답 실패: {e}")
        return f"[오류] Gemini 응답 실패: {str(e)}"

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