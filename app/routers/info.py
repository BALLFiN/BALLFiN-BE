from fastapi import APIRouter, HTTPException, Query
import yfinance as yf
import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from app.db.mongo import company_collection, stock_collection  # 가정: DB 컬렉션은 여기서 가져옵니다.
from pymongo import DESCENDING, ASCENDING
import pandas as pd
import talib
from app.services.financial_analysis import get_yahoo_data, get_interest_rate, fetch_stock_data, combine_all_data, get_stock_info_yfinance, llm_analysis

router = APIRouter(tags=["Info"])

# 티커 심볼 매핑
TICKERS = {
    "kospi": "^KS11",           # 코스피
    "nasdaq": "^IXIC",          # 나스닥
    "usd_krw": "USDKRW=X",      # 원달러 환율
    "oil": "CL=F",              # WTI 원유
    # "gold": "GC=F",             # 금
    "vix": "^VIX",              # VIX 지수
    # "bitcoin": "BTC-USD",       # 비트코인
    # "ethereum": "ETH-USD"       # 이더리움
}

TICKER_TO_INDUSTRY = {
    # 반도체 & IT 하드웨어
    "005930": "반도체 & IT 하드웨어", "000660": "반도체 & IT 하드웨어", "066570": "반도체 & IT 하드웨어",
    "009150": "반도체 & IT 하드웨어", "034220": "반도체 & IT 하드웨어", "018260": "반도체 & IT 하드웨어",
    "064350": "반도체 & IT 하드웨어", "064400": "반도체 & IT 하드웨어", "022100": "반도체 & IT 하드웨어",

    # 인터넷 & 플랫폼
    "035420": "인터넷 & 플랫폼", "035720": "인터넷 & 플랫폼", "323410": "인터넷 & 플랫폼",
    "377300": "인터넷 & 플랫폼",

    # 자동차 & 부품
    "005380": "자동차 & 부품", "000270": "자동차 & 부품", "012330": "자동차 & 부품",
    "086280": "자동차 & 부품", "161390": "자동차 & 부품",

    # 바이오 & 제약
    "207940": "바이오 & 제약", "068270": "바이오 & 제약", "000100": "바이오 & 제약",
    "196170": "바이오 & 제약", "028300": "바이오 & 제약", "042700": "바이오 & 제약",

    # 금융
    "105560": "금융", "055550": "금융", "086790": "금융", "138040": "금융",
    "316140": "금융", "024110": "금융", "006800": "금융", "005940": "금융",
    "016360": "금융", "071050": "금융", "032830": "금융", "000810": "금융",
    "005830": "금융", "029780": "금융", "088980": "금융",

    # 2차전지 & 소재
    "373220": "2차전지 & 소재", "006400": "2차전지 & 소재", "051910": "2차전지 & 소재",
    "003670": "2차전지 & 소재", "096770": "2차전지 & 소재", "247540": "2차전지 & 소재",
    "086520": "2차전지 & 소재", "011790": "2차전지 & 소재",

    # 방산 & 중공업 & 조선
    "012450": "방산 & 중공업 & 조선", "047810": "방산 & 중공업 & 조선", "079550": "방산 & 중공업 & 조선",
    "272210": "방산 & 중공업 & 조선", "042660": "방산 & 중공업 & 조선", "009540": "방산 & 중공업 & 조선",
    "010140": "방산 & 중공업 & 조선", "010620": "방산 & 중공업 & 조선", "329180": "방산 & 중공업 & 조선",
    "034020": "방산 & 중공업 & 조선", "326030": "방산 & 중공업 & 조선", "267250": "방산 & 중공업 & 조선",
    "443060": "방산 & 중공업 & 조선", "000720": "방산 & 중공업 & 조선", "028050": "방산 & 중공업 & 조선",

    # 로봇
    "241560": "로봇", "277810": "로봇",

    # 통신
    "017670": "통신", "030200": "통신", "032640": "통신", "402340": "통신",

    # 게임 & 엔터테인먼트
    "352820": "게임 & 엔터테인먼트", "259960": "게임 & 엔터테인먼트", "251270": "게임 & 엔터테인먼트",

    # 지주사 & 기타
    "005490": "지주사 & 기타", "028260": "지주사 & 기타", "034730": "지주사 & 기타", "003550": "지주사 & 기타",
    "000150": "지주사 & 기타", "001040": "지주사 & 기타", "006260": "지주사 & 기타", "078930": "지주사 & 기타",

    # 소비재
    "097950": "소비재", "271560": "소비재", "003230": "소비재", "090430": "소비재",
    "051900": "소비재", "033780": "소비재", "021240": "소비재",

    # 운송
    "003490": "운송", "011200": "운송", "180640": "운송",

    # 화학 & 철강 & 에너지
    "010130": "화학 & 철강 & 에너지", "298040": "화학 & 철강 & 에너지", "009830": "화학 & 철강 & 에너지",
    "010950": "화학 & 철강 & 에너지", "015760": "화학 & 철강 & 에너지", "450080": "화학 & 철강 & 에너지",
    "010120": "화학 & 철강 & 에너지",

    # 상사 & 해운
    "047050": "상사 & 해운", "267260": "상사 & 해운",
}

INDUSTRY_GROUPS = {
    "반도체 & IT 하드웨어": [
        "005930", "000660", "066570", "009150", "034220", "018260", "064350",
        "064400", "022100"
    ],
    "인터넷 & 플랫폼": ["035420", "035720", "323410", "377300"],
    "자동차 & 부품": ["005380", "000270", "012330", "086280", "161390"],
    "바이오 & 제약": ["207940", "068270", "000100", "196170", "028300", "042700"],
    "금융": [
        "105560", "055550", "086790", "138040", "316140", "024110", "006800",
        "005940", "016360", "071050", "032830", "000810", "005830", "029780",
        "088980"
    ],
    "2차전지 & 소재": [
        "373220", "006400", "051910", "003670", "096770", "247540", "086520",
        "011790"
    ],
    "방산 & 중공업 & 조선": [
        "012450", "047810", "079550", "272210", "042660", "009540", "010140",
        "010620", "329180", "034020", "326030", "267250", "443060", "000720",
        "028050"
    ],
    "로봇": ["241560", "277810"],
    "통신": ["017670", "030200", "032640", "402340"],
    "게임 & 엔터테인먼트": ["352820", "259960", "251270"],
    "지주사 & 기타": [
        "005490", "028260", "034730", "003550", "000150", "001040", "006260",
        "078930"
    ],
    "소비재": [
        "097950", "271560", "003230", "090430", "051900", "033780", "021240"
    ],
    "운송": ["003490", "011200", "180640"],
    "화학 & 철강 & 에너지": [
        "010130", "298040", "009830", "010950", "015760", "450080", "010120"
    ],
    "상사 & 해운": ["047050", "267260"],
}

    
@router.get("/kospi", summary="코스피 실시간 시세")
async def get_kospi():
    """코스피 지수 실시간 시세"""
    data = get_yahoo_data(TICKERS["kospi"])
    return {"name": "코스피", "symbol": "^KS11", **data}

@router.get("/nasdaq", summary="나스닥 실시간 시세") 
async def get_nasdaq():
    """나스닥 지수 실시간 시세"""
    data = get_yahoo_data(TICKERS["nasdaq"])
    return {"name": "나스닥", "symbol": "^IXIC", **data}

@router.get("/usd-krw", summary="원달러 환율 실시간 시세")
async def get_usd_krw():
    """원달러 환율 실시간 시세"""
    data = get_yahoo_data(TICKERS["usd_krw"])
    return {"name": "원달러환율", "symbol": "USDKRW=X", **data}

@router.get("/oil", summary="WTI 원유 실시간 시세")
async def get_oil():
    """WTI 원유 실시간 시세"""
    data = get_yahoo_data(TICKERS["oil"])
    return {"name": "WTI원유", "symbol": "CL=F", **data}

@router.get("/gold", summary="금 실시간 시세")
async def get_gold():
    """금 실시간 시세"""
    data = get_yahoo_data(TICKERS["gold"])
    return {"name": "금", "symbol": "GC=F", **data}

@router.get("/vix", summary="VIX 지수 실시간 시세")
async def get_vix():
    """VIX 지수 실시간 시세"""
    data = get_yahoo_data(TICKERS["vix"])
    return {"name": "VIX지수", "symbol": "^VIX", **data}

@router.get("/bitcoin", summary="비트코인 실시간 시세")
async def get_bitcoin():
    """비트코인 실시간 시세"""
    data = get_yahoo_data(TICKERS["bitcoin"])
    return {"name": "비트코인", "symbol": "BTC-USD", **data}

@router.get("/ethereum", summary="이더리움 실시간 시세")
async def get_ethereum():
    """이더리움 실시간 시세"""
    data = get_yahoo_data(TICKERS["ethereum"])
    return {"name": "이더리움", "symbol": "ETH-USD", **data}

@router.get("/interest-rate", summary="한국은행 기준금리")
async def get_base_rate():
    """한국은행 기준금리"""
    data = get_interest_rate()
    return {"name": "한국은행기준금리", **data}

@router.get("/all", summary="모든 시세 한번에 조회")
async def get_all_prices():
    """모든 금융 상품 시세를 한번에 조회"""
    results = {}
    
    # Yahoo Finance 데이터
    for name, symbol in TICKERS.items():
        data = get_yahoo_data(symbol)
        results[name] = {
            "name": name,
            "symbol": symbol,
            **data
        }
    
    # 기준금리 추가
    rate_data = get_interest_rate()
    results["interest_rate"] = {
        "name": "한국은행기준금리",
        **rate_data
    }
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_symbols": len(results),
        "data": results
    }

@router.get(
    "/companies",
    summary="전체 회사 시장 데이터 조회 (단순 버전)",
    description="""
    MongoDB의 'company' 컬렉션에서 모든 회사의 시장 정보를 조회합니다.
    Pydantic 모델을 사용하지 않고 순수 딕셔너리 리스트를 반환합니다.

    **정렬 기준 (`sort_by`)**:
    - `market_cap_desc`: 시가총액 높은 순 (기본값)
    - `market_cap_asc`: 시가총액 낮은 순
    - `change_percent_desc`: 등락률 높은 순
    - `change_percent_asc`: 등락률 낮은 순
    - `volume_desc`: 거래량 많은 순
    - `volume_asc`: 거래량 적은 순
    """
)
def get_all_company_data(
    sort_by: str = Query("market_cap_desc", description="정렬 기준")
):
    # 정렬 옵션 매핑
    sort_map = {
        "market_cap_desc": [("market_data.market_cap_billion", DESCENDING)],
        "market_cap_asc": [("market_data.market_cap_billion", ASCENDING)],
        "change_percent_desc": [("market_data.change_percent", DESCENDING)],
        "change_percent_asc": [("market_data.change_percent", ASCENDING)],
        "volume_desc": [("market_data.volume", DESCENDING)],
        "volume_asc": [("market_data.volume", ASCENDING)],
    }

    # 유효하지 않은 정렬 기준이 들어올 경우 오류 처리
    if sort_by not in sort_map:
        raise HTTPException(
            status_code=400, 
            detail=f"잘못된 정렬 기준입니다. 사용 가능한 값: {list(sort_map.keys())}"
        )

    sort_option = sort_map[sort_by]

    # MongoDB에서 데이터 조회 및 정렬
    try:
        cursor = company_collection.find({
            "market_data": {"$exists": True, "$ne": None}
        }).sort(sort_option)
        
        companies = list(cursor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 조회 중 오류 발생: {e}")

    if not companies:
        return []

    # 클라이언트에게 보낼 데이터(순수 딕셔너리) 형식으로 가공
    results = []
    for company in companies:
        # market_data 필드가 없는 문서에 대한 안전장치
        market_data = company.get("market_data", {}) 
        
        change_percent_val = market_data.get("change_percent")
        change_percent_rounded = round(change_percent_val, 2) if change_percent_val is not None else None
        
        market_cap_billion_val = market_data.get("market_cap_billion")
        market_cap_rounded = round(market_cap_billion_val, 2) if market_cap_billion_val is not None else None
        
        results.append({
            "corp_name": company.get("corp_name"),
            "stock_code": company.get("stock_code"),
            "current_price": market_data.get("current_price"),
            "change": market_data.get("change"),
            "change_percent": change_percent_rounded,
            "week_52_high": market_data.get("week_52_high"),
            "week_52_low": market_data.get("week_52_low"),
            "volume": market_data.get("volume"),
            "market_cap_billion": market_cap_rounded
        })
        
    return results

@router.get(
    "/related-companies/{stock_code}",
    summary="관련 기업 목록 조회",
    description="""
    기준이 되는 종목 코드(stock_code)를 입력받아, 동일한 산업군에 속한 관련 기업들의 시장 정보를 반환합니다.
    정렬 기능은 `/companies`와 동일하게 제공됩니다.
    """
)
def get_related_companies(
    stock_code: str,
    sort_by: str = Query("market_cap_desc", description="정렬 기준")
):
    # 1. 입력된 stock_code를 기반으로 해당 기업의 산업군 찾기
    industry = TICKER_TO_INDUSTRY.get(stock_code)
    if not industry:
        raise HTTPException(
            status_code=404, 
            detail=f"종목 코드 '{stock_code}'에 대한 산업군 정보를 찾을 수 없습니다."
        )

    # 2. 같은 산업군에 속한 다른 기업들의 종목 코드 목록 가져오기
    related_tickers = INDUSTRY_GROUPS.get(industry, [])
    if not related_tickers:
        return []

    # 3. 정렬 옵션 설정 (기존 코드 재사용)
    sort_map = {
        "market_cap_desc": [("market_data.market_cap_billion", DESCENDING)],
        "market_cap_asc": [("market_data.market_cap_billion", ASCENDING)],
        "change_percent_desc": [("market_data.change_percent", DESCENDING)],
        "change_percent_asc": [("market_data.change_percent", ASCENDING)],
        "volume_desc": [("market_data.volume", DESCENDING)],
        "volume_asc": [("market_data.volume", ASCENDING)],
    }
    if sort_by not in sort_map:
        raise HTTPException(
            status_code=400, 
            detail=f"잘못된 정렬 기준입니다. 사용 가능한 값: {list(sort_map.keys())}"
        )
    sort_option = sort_map[sort_by]

    # 4. MongoDB에서 관련 기업들의 데이터 한번에 조회
    try:
        query = {
            "stock_code": {"$in": related_tickers},
            "market_data": {"$exists": True, "$ne": None}
        }
        cursor = company_collection.find(query).sort(sort_option)
        companies = list(cursor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터베이스 조회 중 오류 발생: {e}")

    if not companies:
        return []

    # 5. 클라이언트에 보낼 데이터 형식으로 가공 (기존 코드 재사용)
    results = []
    for company in companies:
        market_data = company.get("market_data", {}) 
        
        change_percent_val = market_data.get("change_percent")
        change_percent_rounded = round(change_percent_val, 2) if change_percent_val is not None else None
        
        market_cap_billion_val = market_data.get("market_cap_billion")
        market_cap_rounded = round(market_cap_billion_val, 2) if market_cap_billion_val is not None else None
        
        results.append({
            "corp_name": company.get("corp_name"),
            "stock_code": company.get("stock_code"),
            "current_price": market_data.get("current_price"),
            "change": market_data.get("change"),
            "change_percent": change_percent_rounded,
            "week_52_high": market_data.get("week_52_high"),
            "week_52_low": market_data.get("week_52_low"),
            "volume": market_data.get("volume"),
            "market_cap_billion": market_cap_rounded
        })
        
    return results

@router.get(
    "/stock/{stock_code}", 
    summary="개별 주식 상세페이지의 주가정보를 제공하는 api",
    description="경로 파라미터로 stock_code를 입력받아 상세한 주가정보를 제공하는 api"
)
async def get_stock_data(stock_code: str):
    try:
        # 1. 데이터 조회 시도
        result, _ = get_stock_info_yfinance(stock_code)

        # 2. 결과가 유효한지 확인
        # get_stock_info_yfinance 함수가 실패 시 {'error': '...'}를 반환한다고 가정
        if not result or result.get("error"):
            # 404 Not Found: 클라이언트가 잘못된 종목 코드를 요청
            raise HTTPException(
                status_code=404, 
                detail=f"종목 코드 '{stock_code}'에 대한 정보를 찾을 수 없습니다."
            )
        
        # 3. 정상 결과 반환
        return result

    except Exception as e:
        # 500 Internal Server Error: 그 외 모든 예상치 못한 서버 오류
        # 서버 로그에 에러를 기록하는 것이 좋습니다 (예: logging.error(e))
        print(f"Server Error for /stock/{stock_code}: {e}") # 콘솔 로그
        raise HTTPException(
            status_code=500,
            detail="서버 내부 오류가 발생했습니다. 관리자에게 문의해주세요."
        )


@router.get(
    "/company/{stock_code}", 
    summary="개별 주식 상세페이지의 기술적 분석, 재무분석 페이지의 데이터를 제공하는 api",
    description="경로 파라미터로 stock_code를 입력받아 기술적 분석, 재무분석 페이지의 데이터를 제공하는 api"
)
async def get_company_data(stock_code: str):
    try:
        # 1. DB에서 데이터 조회 시도
        financial_df = fetch_stock_data(stock_collection, stock_code)

        # 2. DB 조회 결과가 비어있는지 확인
        if financial_df is None or financial_df.empty:
            # 404 Not Found: DB에 해당 종목 데이터가 없음
            raise HTTPException(
                status_code=404,
                detail=f"데이터베이스에서 '{stock_code}'에 대한 재무 데이터를 찾을 수 없습니다."
            )

        # 3. 데이터 가공 및 분석
        result = combine_all_data(financial_df, stock_code)
        
        # 4. 최종 결과 반환
        return result

    except HTTPException as e:
        # HTTPException은 그대로 다시 발생시켜 FastAPI가 처리하도록 함
        raise e
    except Exception as e:
        # 500 Internal Server Error: DB 연결 실패, combine_all_data 함수 오류 등
        print(f"Server Error for /company/{stock_code}: {e}") # 콘솔 로그
        raise HTTPException(
            status_code=500,
            detail="데이터 처리 중 서버 내부 오류가 발생했습니다."
        )

@router.get(
    "/total_analysis/{stock_code}",
    summary="개별 주식 상세페이지의 기술적 분석, 재무분석 페이지의 데이터를 llm으로 분석하여 제공하는 함수",
    description="종목 코드를 받아 펀더멘털 및 기술적 지표를 LLM이 종합적으로 분석한 결과를 제공합니다."
)
async def get_llm_stock_analysis(stock_code: str):
    try:
        # 1. 핵심 로직인 llm_analysis 함수 호출
        result = llm_analysis(stock_code)

        # 2. 함수 반환 값에 'error' 키가 있는지 확인하여 성공/실패 분기 처리
        if 'error' in result:
            # llm_analysis 함수 내부에서 에러가 발생하여 {'error': ...}를 반환한 경우
            # 예를 들어, 분석에 필요한 데이터가 부족한 경우
            print(f"Analysis Error for /analysis/llm/{stock_code}: {result['error']}") # 콘솔 로그
            raise HTTPException(
                status_code=422, # 422: Unprocessable Entity (요청은 잘 됐으나, 내용이 처리 불가능)
                detail=result['error']
            )
        
        # 3. 성공 시, LLM 분석 결과 반환
        return result

    except HTTPException as e:
        # 위에서 발생시킨 HTTPException을 그대로 전달
        raise e
    except Exception as e:
        # llm_analysis 함수 실행 중 예상치 못한 에러가 발생한 경우 (DB 접속 실패 등)
        # 500 Internal Server Error 반환
        print(f"Server Error for /analysis/llm/{stock_code}: {e}") # 콘솔 로그
        raise HTTPException(
            status_code=500,
            detail="분석 데이터를 생성하는 중 서버 내부 오류가 발생했습니다."
        )

