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
from app.services.financial_analysis import get_yahoo_data, get_interest_rate

router = APIRouter()

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

