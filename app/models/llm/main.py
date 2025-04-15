from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
from app.models.llm.chat_service import query_news
# FastAPI 앱
app_chat = FastAPI()

# CORS 미들웨어 추가
app_chat.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 오리진 허용 (개발 환경용)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

@app_chat.post("/avatarchat/api/chat")
async def chat(request: Request):
    data = await request.json()
    messages = data.get('messages')
    
    if not messages:
        raise HTTPException(status_code=400, detail="메시지가 제공되지 않았습니다.")
    
    # 사용자 입력 처리
    user_input = messages[0]['content']
    
    # 뉴스 데이터베이스 쿼리
    result = query_news(user_input)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    
    response_content = {
        "model": "gemini-1.5-flash",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "message": {"role": "assistant", "content": result["response"]},
        "sources": result.get("sources", []),
        "done": True
    }
    
    return JSONResponse(content=response_content)

# 직접 실행시 테스트용 코드
if __name__ == "__main__":
    # 테스트 쿼리
    test_query = "최근 삼성전자 뉴스는 무엇인가요?"
    print(f"테스트 쿼리: {test_query}")
    
    try:
        result = query_news(test_query)
        if result["status"] == "success":
            print(f"\n응답: {result['response']}")
            print(f"\n참고 소스: {result['sources']}")
        else:
            print(f"\n오류: {result['message']}")
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
    
    # FastAPI 서버 실행
    import uvicorn
    uvicorn.run(app_chat, host="0.0.0.0", port=5001)