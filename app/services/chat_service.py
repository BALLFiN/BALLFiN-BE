from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ 일반 호출 (한 번에 전체 답변 받기)
async def ask_llm(prompt: str) -> str:
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

# ✅ 스트리밍 호출 (조각조각 답변 받기)
async def stream_llm(prompt: str):
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