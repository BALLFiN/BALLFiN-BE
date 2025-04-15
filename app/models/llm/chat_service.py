from app.models.llm.DB_loader import load_vectordb
from app.models.llm.graph import create_langgraph
from langchain_core.messages import HumanMessage
from typing import Dict

# 응답 생성을 위한 도구 함수
def query_news(query: str) -> Dict:
    """뉴스 데이터베이스를 쿼리하고 LangGraph를 사용해 응답을 생성하는 도구"""
    # VectorDB 로드
    vectordb = load_vectordb()
    if not vectordb:
        return {"status": "error", "message": "벡터 데이터베이스를 로드할 수 없습니다."}
    
    # 검색기 설정
    retriever = vectordb.as_retriever(search_type="similarity", search_kwargs={"k": 10})
    
    # LangGraph 생성
    graph = create_langgraph(retriever)
    
    # 초기 상태 설정
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "query": query,
    }
    
    try:
        print("📤 Graph 실행 중...")
        # 그래프 실행
        result = graph.invoke(initial_state)
        
        # 관련 문서 메타데이터 추출
        sources = []
        if "context" in result and result["context"]:
            for doc in result["context"]:
                sources.append(doc.metadata)
        
        return {
            "status": "success",
            "response": result["response"],
            "sources": sources
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_message = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
        print(error_message)
        return {"status": "error", "message": error_message}

