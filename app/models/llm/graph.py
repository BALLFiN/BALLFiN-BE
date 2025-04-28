from typing import List
import os

from app.models.llm.DB_loader import load_vectordb
from langchain_community.tools.tavily_search import TavilySearchResults
from app.models.llm.knowledge_graph import create_graph_structure

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI  
from langchain.agents import Tool
from langgraph.prebuilt import create_react_agent

vectordb = load_vectordb()
print("✅ VectorDB 로드 완료")
retriever = vectordb.as_retriever(search_type="similarity", search_kwargs={"k": 5})

#  문서 검색 도구
def news_retrieve(query) -> List[Document]:
    print("✅ 뉴스 문서 검색 도구 사용")
    try:
        docs = retriever.invoke(query)
        return docs
    except Exception as e:
        print("❌ 문서 검색 중 오류:", e)
        return "문서 검색 중 오류 발생"

# 웹 검색 도구
tavily_tool = TavilySearchResults(   # BaseTool 구현체
    name="web_search",
    description="실시간 웹 검색을 수행합니다.",
    max_results=3,
    api_key = os.getenv("TAVILY_API_KEY")
)

def create_agent(
        llm : ChatOpenAI | ChatGoogleGenerativeAI,
):

    # Tools
    tools = [
        tavily_tool,
        Tool(
            name = "news_retrieve",
            func = news_retrieve,
            description="기업 뉴스 DB에서 주요 뉴스를 찾습니다"),
        Tool(
            name = "create_graph_structure",
            func = create_graph_structure,
            description="기업/뉴스 분석에 필요한 배경 지식그래프를 만듭니다"),
    ]

    # Agent
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt='''
            당신은 금융·경제 분석 전문 에이전트입니다.
            사용 가능한 도구:
            tavily_tool : 실시간 웹 검색
            news_retrieve: 기업 뉴스 DB에서 주요 뉴스를 찾습니다.
            create_graph_structure: 기업/뉴스 분석에 필요한 배경 지식그래프를 만듭니다.

            정보를 충분히 모은 후 답변을 생성하세요.
        '''
    )

    return agent