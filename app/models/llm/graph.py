from langchain_core.documents import Document
from typing import List, Any, Optional, TypedDict
from google.generativeai import GenerativeModel
from app.models.llm.config import GEMINI_MODEL
import google.generativeai as genai
import langgraph.graph as lg
from app.models.llm.config import GEMINI_API_KEY


genai.configure(api_key=GEMINI_API_KEY)

# LangGraph 상태 정의
class GraphState(TypedDict):
    messages: List[Any]
    query: str
    context: Optional[List[Document]]
    response: Optional[str]

# LangGraph 노드 함수: 문서 검색
def retrieve(state: GraphState, retriever) -> GraphState:
    try:
        query = state["query"]
        docs = retriever.invoke(query)
        return {"context": docs, **state}
    except Exception as e:
        print("❌ 문서 검색 중 오류:", e)
        raise

# LangGraph 노드 함수: 응답 생성
def generate_response(state: GraphState) -> GraphState:
    """검색된 문서와 쿼리를 기반으로 응답을 생성합니다."""
    try:
        # 최신 Gemini API 사용
        model = genai.GenerativeModel(GEMINI_MODEL)

        # 상태에서 메시지와 문서 가져오기
        context = state.get("context", [])

        # 문서 내용 추출
        context_text = "\n\n".join([doc.page_content for doc in context]) if context else ""

        # 사용자 쿼리 추출
        query = state.get("query", "")

        # 안전하게 API 호출
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }

        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]

        prompt = f"""
        다음 뉴스 정보를 기반으로 사용자의 질문에 답변하세요.
        뉴스 정보를 바탕으로 정확하게 답변해주세요.
        사용자 질문에서 어떤 대상에 대한 질문인지 집중하고 뉴스를 내용을 선별하세요.
        알지 못하는 내용은 모른다라고 대답하세요.
        
        사용자 질문: {query}

        관련 뉴스 정보:
        {context_text}
        """

        # Gemini API 호출
        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        # 응답 텍스트 추출
        response_text = response.text if hasattr(response, 'text') else str(response)
        
        #디버깅
        #print(f"🔍 Gemini Prompt:\n{prompt}")
        #print(f"🧠 Gemini 응답:\n{response.text}")
        
        return {"response": response_text, **state}
    except Exception as e:
        error_message = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
        print(error_message)
        return {"response": error_message, **state}

# LangGraph 생성 함수
def create_langgraph(retriever):
    """LangGraph를 생성하고 컴파일합니다."""
    builder = lg.StateGraph(GraphState)
    
    # retriever 함수에 retriever 객체를 전달하기 위한 래퍼 함수
    def retrieve_with_retriever(state):
        return retrieve(state, retriever)
    
    # 노드 추가
    builder.add_node("retrieve", retrieve_with_retriever)
    builder.add_node("generate", generate_response)
    
    # 엣지 설정
    builder.set_entry_point("retrieve")
    builder.add_edge("retrieve", "generate")
    builder.set_finish_point("generate")
    
    # 그래프 컴파일
    return builder.compile()
