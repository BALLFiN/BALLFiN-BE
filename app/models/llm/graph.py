from typing import List
import os

from app.models.llm.DB_loader import load_vectordb
from langchain_community.tools.tavily_search import TavilySearchResults
# from app.models.llm.knowledge_graph import create_graph_structure

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI  
from langchain.agents import Tool
from langgraph.prebuilt import create_react_agent
from typing import Union

vectordb = load_vectordb()
print("✅ VectorDB 로드 완료")
retriever = vectordb.as_retriever(search_type="similarity", search_kwargs={"k": 5})

tavily_tool = TavilySearchResults(   # BaseTool 구현체
    name="web_search",
    description="실시간 웹 검색을 수행합니다.",
    max_results=3,
    api_key = os.getenv("TAVILY_API_KEY")
)

#  문서 검색 도구 
def news_retrieve(query) -> List[Document]:
    print("✅ 뉴스 문서 검색 도구 사용")
    try:
        docs = retriever.invoke(query)
        return docs
    except Exception as e:
        print("❌ 문서 검색 중 오류:", e)
        return "문서 검색 중 오류 발생"

# 웹 검색 도구 / 실행 여부를 확인하기 위해 랩핑
def web_search(query: str):
    """검색 결과를 반환."""
    print("🔍 웹 검색 도구 사용 ", query)
    docs = tavily_tool.invoke(query)
    return docs



def create_agent(
        llm: Union[ChatOpenAI, ChatGoogleGenerativeAI]
):

    # Tools
    tools = [
        Tool(
            name = "web_search",
            func = web_search,
             description="실시간 웹 검색을 수행합니다."),
        # Tool(
        #     name = "news_retrieve",
        #     func = news_retrieve,
        #     description="기업 뉴스 DB에서 주요 뉴스를 찾습니다"),
        # Tool(
        #     name = "create_graph_structure",
        #     func = create_graph_structure,
        #     description="기업/뉴스 분석에 필요한 배경 지식그래프를 만듭니다"),
    ]

    # Agent
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt='''
            당신은 금융·경제 분석 전문가입니다. 
            정보를 충분히 모은 후 답변을 생성하세요.
            당신이 수집한 정보가 질문과 관련이 있는지 확인하고, 관련이 없으면 다시 수집하세요.
        '''
    )

    return agent