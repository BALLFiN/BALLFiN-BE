from fastapi import APIRouter, HTTPException
import yfinance as yf
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

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

def get_yahoo_data(symbol: str):
    """Yahoo Finance에서 단일 심볼 데이터 조회"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        info = ticker.info
        print(hist)
        print(info)
        if hist.empty:
            return {"error": "데이터 없음"}
        
        current_price = hist['Close'].iloc[-1]
        prev_close = info.get('previousClose', current_price)
        change = current_price - prev_close
        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
        
        return {
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "volume": int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}
    
def get_interest_rate():
    """한국은행 기준금리 조회"""
    api_key = os.getenv("BOK_API_KEY", "M2LOD7ISVP6UWIE1JK1E")
    today = datetime.now().strftime("%Y%m%d")
    
    # 최근 30일 데이터 조회
    start_date = datetime.now().replace(day=1).strftime("%Y%m%d")
    url = f'https://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/100/722Y001/D/{start_date}/{today}/0101000'
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'StatisticSearch' in data and 'row' in data['StatisticSearch']:
                print(data)
                rate_data = data['StatisticSearch']['row'][-1]
                return {
                    "rate": float(rate_data['DATA_VALUE']),
                    "date": rate_data['TIME'],
                    "timestamp": datetime.now().isoformat()
                }
        return {"error": "데이터 조회 실패"}
    except Exception as e:
        return {"error": str(e)}
    
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