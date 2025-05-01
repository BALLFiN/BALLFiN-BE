from typing import List, Dict, TypedDict, Annotated, Literal
import os
import json
import time

from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END

load_dotenv()

# 분류 카테고리 정의
class NewsCategory(TypedDict):
    category: str  # 카테고리 코드 (예: "P1", "I1", "C1" 등)
    textinformation: str  # 세부 카테고리 내용
    confidence: float  # 신뢰도 점수 (0.0~1.0)
    reason: str  # 분류 이유에 대한 설명

class GraphState(TypedDict):
    """상태 객체"""
    news_text: str
    extracted_info: Dict
    classification_result: NewsCategory

# 1. 정보 추출 노드: 뉴스 텍스트에서 핵심 정보 추출
def extract_key_information(state: GraphState) -> GraphState:
    news_text = state.get("news_text", "")
    print(f"📝 전달된 뉴스 길이: {len(news_text)} 자")
    print(f"📝 전달된 뉴스 일부: {news_text[:100]}...")
    
    if not news_text or len(news_text) < 10:  # 너무 짧은 텍스트는 처리하지 않음
        print("⚠️ 뉴스 텍스트가 없거나 너무 짧습니다")
        return {
            "news_text": news_text,
            "extracted_info": {
                "main_parties": "제공된 뉴스 텍스트 없음",
                "key_issue": "제공된 뉴스 텍스트 없음",
                "affected_industries": "제공된 뉴스 텍스트 없음",
                "key_figures": "제공된 뉴스 텍스트 없음"
            }
        }
    
    # OpenAI API 직접 호출 방식으로 변경
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",  # 더 안정적인 모델 사용
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0,
    )
    
    messages = [
        SystemMessage(content="""
        당신은 뉴스 기사에서 핵심 정보를 추출하는 전문가입니다.
        주어진 기사에서 다음 정보를 추출하고 정확히 JSON 형식으로만 응답하세요:
        1. 주요 당사자(기업, 정부 기관, 인물, 그 외에 예상 기업 등)
        2. 핵심 사건 또는 이슈
        3. 영향을 받는 산업 또는 분야
        4. 주요 수치나 변화 (있는 경우)
        
        다음 형식으로만 응답하세요. 다른 설명이나 텍스트는 포함하지 마세요:
        {
          "main_parties": "주요 당사자 리스트",
          "key_issue": "핵심 사건/이슈",
          "affected_industries": "영향 받는 산업/분야",
          "key_figures": "주요 수치나 변화"
        }
        """),
        HumanMessage(content=f"다음 뉴스 기사를 분석해주세요:\n\n{news_text}")
    ]
    
    try:
        # API 호출 시도
        response = llm.invoke(messages)
        response_text = response.content
        
        # JSON 파싱 시도
        try:
            # 응답에서 JSON 부분만 추출 (마크다운 코드 블록이 있을 경우)
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_text = response_text.strip()
            
            extracted_info = json.loads(json_text)
            print("✅ JSON 파싱 성공:", extracted_info)
        except Exception as e:
            print(f"⚠️ JSON 파싱 오류: {e}")
            print(f"원본 응답: {response_text}")
            
            # 기본값 설정
            extracted_info = {
                "main_parties": "파싱 실패 - 원본 응답 확인 필요",
                "key_issue": "파싱 실패 - 원본 응답 확인 필요",
                "affected_industries": "파싱 실패 - 원본 응답 확인 필요",
                "key_figures": "파싱 실패 - 원본 응답 확인 필요"
            }
            
            # JSON 형식이 아닌 일반 텍스트에서 정보 추출 시도
            if "주요 당사자" in response_text or "핵심 사건" in response_text:
                lines = response_text.split("\n")
                for line in lines:
                    if "주요 당사자" in line:
                        extracted_info["main_parties"] = line.split(":", 1)[1].strip() if ":" in line else line
                    elif "핵심 사건" in line or "핵심 이슈" in line:
                        extracted_info["key_issue"] = line.split(":", 1)[1].strip() if ":" in line else line
                    elif "영향" in line and "산업" in line:
                        extracted_info["affected_industries"] = line.split(":", 1)[1].strip() if ":" in line else line
                    elif "주요 수치" in line:
                        extracted_info["key_figures"] = line.split(":", 1)[1].strip() if ":" in line else line
    
    except Exception as e:
        print(f"⚠️ API 호출 오류: {e}")
        extracted_info = {
            "main_parties": "API 호출 실패",
            "key_issue": "API 호출 실패",
            "affected_industries": "API 호출 실패",
            "key_figures": "API 호출 실패"
        }
    
    print("✅ 핵심 정보 추출 완료")
    return {"news_text": news_text, "extracted_info": extracted_info}

# 2. 분류 노드: 주어진 카테고리에 따라 뉴스 분류
def classify_news(state: GraphState) -> GraphState:
    """추출된 정보를 바탕으로 뉴스를 분류하는 노드"""
    news_text = state.get("news_text", "")
    extracted_info = state.get("extracted_info", {})
    
    print(f"📊 분류 단계에 전달된 추출 정보: {extracted_info}")
    
    # 텍스트가 없거나 추출된 정보가 기본값인 경우 기본 분류 결과 반환
    if not news_text or "API 호출 실패" in extracted_info.get("main_parties", ""):
        classification_result = {
            "category": "ERROR",
            "textinformation": "데이터 부족",
            "confidence": 0.0,
            "reason": "뉴스 텍스트 또는 추출된 정보가 없습니다."
        }
        return {
            "news_text": news_text,
            "extracted_info": extracted_info,
            "classification_result": classification_result
        }
    
    # OpenAI API 직접 호출
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",  # 더 안정적인 모델로 변경
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0,
    )
    
    category_info = """
    P1. 관세 정책 변화: 수출입 관세 인상/인하 관련 정부 발표
    P2. 정부 보조금/지원 정책: 특정 산업/기업에 대한 보조금, 세제 혜택 등 공식 발표
    P3. 규제 강화: 특정 산업군에 대한 규제 강화 법안 통과/시행 발표
    
    I1. 원자재 가격 급등락: 국제 유가, 희토류 등 원자재 가격 10% 이상 급등락
    I2. 공급망 붕괴: 핵심 부품/자재 공급 차질, 생산 중단 사태
    
    C1. 대형 계약 체결: 기업 간 대규모 B2B 계약, 공급/납품 계약 공시
    C2. 인수합병(M&A): 공식화된 인수합병 발표
    C3. 경쟁사 부도/리콜: 동종 업계 경쟁사 위기(부도, 리콜, 회계비리 등)
    C4. 주요 제품 출시: 시장 기대 초과 신제품 발표
    C5. 대주주 지분 매각: 주요 주주/창업주의 5% 이상 지분 매각 공시
    C6. 공매도 증가: 특정 종목 공매도 거래량/잔고 비율 급증
    """
    
    # 추출된 정보를 문자열로 변환
    extracted_info_str = "\n".join([f"{k}: {v}" for k, v in extracted_info.items()])
    
    messages = [
        SystemMessage(content=f"""
        당신은 금융·경제 뉴스 분류 전문가입니다.
        주어진 정보를 바탕으로 뉴스를 다음 카테고리 중 하나로 정확히 분류하세요:
        
        {category_info}
        
        위 카테고리에 맞지 않으면 'OTHER'로 분류하세요.
        
        다음 JSON 형식으로만 응답하세요. 추가 설명이나 텍스트는 포함하지 마세요:
        {{
            "category": "카테고리 코드 (예: P1, I2, C3 등, 또는 'OTHER')",
            "textinformation": "세부 카테고리 내용 (예: '관세 정책 변화', '공급망 붕괴' 등)",
            "confidence": 신뢰도 점수 (0.0~1.0),
            "reason": "분류 이유에 대한 간략한 설명"
        }}
        """),
        HumanMessage(content=f"""
        뉴스 원문: 
        {news_text}
        
        추출된 정보:
        {extracted_info_str}
        """)
    ]
    
    try:
        # API 호출 시도
        response = llm.invoke(messages)
        response_text = response.content
        
        # JSON 파싱 시도
        try:
            # 응답에서 JSON 부분만 추출 (마크다운 코드 블록이 있을 경우)
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_text = response_text.strip()
            
            classification_result = json.loads(json_text)
            print("✅ 분류 결과 JSON 파싱 성공:", classification_result)
        except Exception as e:
            print(f"⚠️ 분류 결과 JSON 파싱 오류: {e}")
            print(f"원본 응답: {response_text}")
            
            # "P1"과 같은 카테고리 코드가 응답에 있는지 확인하여 추출 시도
            categories = ["P1", "P2", "P3", "I1", "I2", "C1", "C2", "C3", "C4", "C5", "C6", "OTHER"]
            found_category = "OTHER"
            for cat in categories:
                if cat in response_text:
                    found_category = cat
                    break
            
            # 기본값 설정
            classification_result = {
                "category": found_category,
                "textinformation": "파싱 실패, 원본 응답 참조",
                "confidence": 0.5,
                "reason": "JSON 파싱 실패, 원본 응답에서 카테고리 추정"
            }
    
    except Exception as e:
        print(f"⚠️ 분류 API 호출 오류: {e}")
        classification_result = {
            "category": "ERROR",
            "textinformation": "API 오류",
            "confidence": 0.0,
            "reason": f"API 호출 중 오류 발생: {str(e)}"
        }
    
    print("✅ 뉴스 분류 완료")
    return {
        "news_text": news_text,
        "extracted_info": extracted_info,
        "classification_result": classification_result
    }

def create_news_classification_agent():
    """뉴스 분류를 위한 그래프 생성"""
    # 워크플로우 그래프 생성
    workflow = StateGraph(GraphState)
    
    # 노드 추가
    workflow.add_node("extract_info", extract_key_information)
    workflow.add_node("classify", classify_news)
    
    # 엣지 설정 (노드 간 연결)
    workflow.add_edge("extract_info", "classify")
    workflow.add_edge("classify", END)
    
    # 시작 노드 설정
    workflow.set_entry_point("extract_info")
    
    # 그래프 컴파일
    graph = workflow.compile()
    
    return graph

# 사용 예시
def classify_news_document(news_text: str):
    """뉴스 문서를 분류하는 함수"""
    print("\n===== 뉴스 분류 시작 =====")
    print(f"입력된 뉴스 길이: {len(news_text)} 자")
    
    # 뉴스 텍스트 전처리
    if isinstance(news_text, str):
        # 줄바꿈 여러 개를 하나로 통합
        news_text = '\n'.join(line for line in news_text.splitlines() if line.strip())
    else:
        news_text = str(news_text)
    
    graph = create_news_classification_agent()
    
    # 초기 상태 설정
    initial_state = {"news_text": news_text}
    
    # 그래프 실행
    try:
        result = graph.invoke(initial_state)
        print("\n===== 뉴스 분류 완료 =====")
        return result
    except Exception as e:
        print(f"⚠️ 그래프 실행 중 오류: {e}")
        # 오류 발생 시 기본 결과 반환
        return {
            "news_text": news_text,
            "extracted_info": {
                "main_parties": "오류 발생",
                "key_issue": "오류 발생",
                "affected_industries": "오류 발생",
                "key_figures": "오류 발생"
            },
            "classification_result": {
                "category": "ERROR",
                "textinformation": "처리 오류",
                "confidence": 0.0,
                "reason": f"처리 중 오류 발생: {str(e)}"
            }
        }