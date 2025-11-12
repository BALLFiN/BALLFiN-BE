import os
from dotenv import load_dotenv
from app.db.mongo import chat_messages
from bson import ObjectId
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from app.models.llm.graph import create_agent,current_kst


load_dotenv()


# langchain 래퍼 모델로 사용해야 랭그래프와 호환 가능함
gpt = ChatOpenAI(
    model="gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY")
    )

# 랭그래프 에이전트로 랩핑
gpt_agent = create_agent(gpt)
print("✅ gpt 에이전트 준비 완료")



def format_history_to_prompt(history: list, current_question: str) -> str:
    dialogue = ""
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        dialogue += f"{role}: {msg['content']}\n"
    dialogue += f"User: {current_question}"
    return dialogue


def prepend_time(p: str) -> str:
    return f"현재 시각은 {current_kst()} KST입니다. 이 시간 기준으로 답변해 주세요.\n{p}"

# ✅ 일반 호출 (한 번에 전체 답변 받기)
async def ask_llm_gpt(prompt: str) -> str:
    """
    GPT-4o에게 질문(prompt)을 보내고 답변을 받아온다. (스트리밍 ❌)
    """
    print("ask to gpt")
    time_prompt = prepend_time(prompt)
    try:
        response = gpt_agent.invoke(
            {"messages": [
                {"role": "user",
                "content": time_prompt}]}
                )
        return response['messages'][-1].content
    
    except Exception as e:
        print(f"[ERROR] Gpt 응답 실패: {e}")
        return f"[오류] Gpt 응답 실패: {str(e)}"


# ✅ LangGraph 토큰 스트리밍 
async def stream_llm_gpt(prompt: str):
    time_prompt = prepend_time(prompt)
    async for msg, _ in gpt_agent.astream(            
        {"messages": [{"role": "user", "content": time_prompt}]},
        stream_mode="messages",
    ):
        if isinstance(msg, AIMessage) and msg.content:
            yield msg.content



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