import yfinance as yf
import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from app.db.mongo import company_collection, stock_collection  # 가정: DB 컬렉션은 여기서 가져옵니다.
from pymongo import DESCENDING, ASCENDING
import pandas as pd
import talib
from pprint import pprint
import numpy as np
import json

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
        
        historical_data = []
        today = datetime.now()
        for i in range(10):
            past_date = today - timedelta(days=i)
            historical_data.append({
                "date": past_date.strftime('%Y-%m-%d'),
                "price": round(current_price, 2)
            })
        
        return {
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "volume": int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0,
            "historical_data": historical_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}
    
def get_interest_rate():
    """한국은행 기준금리 조회"""
    api_key = os.getenv("BOK_API_KEY")
    
    # 최근 30일 데이터 조회
    today = datetime.now().strftime("%Y%m%d")
    start_date = datetime.now().replace(day=1).strftime("%Y%m%d")
    url = f'https://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/100/722Y001/D/{start_date}/{today}/0101000'
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'StatisticSearch' in data and 'row' in data['StatisticSearch']:
                print(data)
                rate_data = data['StatisticSearch']['row'][-1]
                historical_data = []
                base_date = datetime.now()
                for i in range(10):
                    past_date = base_date - timedelta(days=i)
                    historical_data.append({
                        "date": past_date.strftime('%Y-%m-%d'),
                        "rate": float(rate_data['DATA_VALUE'])
                    })               
                return {
                    "rate": float(rate_data['DATA_VALUE']),
                    "historical_data": historical_data,
                    "timestamp": datetime.now().isoformat()
                }
        return {"error": "데이터 조회 실패"}
    except Exception as e:
        return {"error": str(e)}
    
def get_financial_data(stock_code, years_to_fetch=5):
    """
    MongoDB에서 재무 데이터를 가져와 최신 분기 데이터와 최근 N개년 데이터를 반환합니다.

    Args:
        stock_code (str): 조회할 종목 코드.
        years_to_fetch (int, optional): 가져올 최근 데이터의 연 수. 기본값은 5입니다.

    Returns:
        tuple: (최신 분기 데이터, 최근 N개년 데이터) 형태의 튜플.
               데이터 조회나 처리에 실패하면 (None, None)을 반환합니다.
    """
    financial_data = None

    try:
        document = company_collection.find_one({'stock_code': stock_code})
        
        if document:
            financial_data = document.get('financial_data')
        else:
            print(f"⚠️ [{stock_code}] 데이터베이스에서 해당 종목을 찾을 수 없습니다.")
            return None, None
            
    except Exception as e:
        print(f"❌ 데이터베이스 조회 중 오류 발생: {e}")
        return None, None


    # --- 2. 데이터 처리 ---
    if not financial_data:
        # financial_data가 비어있는 경우 처리
        print(f"⚠️ [{stock_code}] 재무 데이터가 비어있습니다.")
        return None, None
        
    try:
        # 2-1. 가장 최신 분기 데이터 가져오기
        latest_quarter = max(financial_data.keys())
        latest_data = financial_data[latest_quarter]

        # 2-2. 최근 N개년 데이터 가져오기
        latest_year = int(latest_quarter[:4])
        start_year = latest_year - years_to_fetch
        recent_n_years_data = {
            quarter: data
            for quarter, data in financial_data.items()
            if int(quarter[:4]) >= start_year
        }
        
        # --- 3. 처리된 두 개의 결과값 반환 ---
        return latest_data, recent_n_years_data

    except Exception as e:
        print(f"❌ [{stock_code}] 데이터 처리 중 오류 발생: {e}")
        return None, None

def fetch_stock_data(stock_collection, stock_code: str, days_to_fetch: int = 120):
    """
    MongoDB에서 특정 종목의 일봉 데이터를 조회하여 DataFrame으로 반환합니다.

    Args:
        stock_collection: MongoDB의 'stock' 컬렉션 객체.
        stock_code (str): 분석할 종목의 코드.
        days_to_fetch (int): 조회할 데이터의 일 수.

    Returns:
        pd.DataFrame: 조회된 주가 데이터. 데이터가 없거나 오류 발생 시 None을 반환합니다.
    """
    try:
        query = {"stock_code": stock_code, "period": "D"}
        cursor = stock_collection.find(query).sort("date", DESCENDING).limit(days_to_fetch)
        raw_data_list = list(cursor)

        if not raw_data_list:
            print(f"⚠️ [{stock_code}] 종목의 데이터를 찾을 수 없습니다.")
            return None

        # 차트와 분석을 위해 시간 순서대로 재정렬 (과거 -> 현재)
        raw_data_list.reverse()
        df = pd.DataFrame(raw_data_list)
        return df

    except Exception as e:
        print(f"❌ DB 조회 중 오류 발생: {e}")
        return None

# ---------------------- 주요 지표 분석 ---------------------- 

def format_history(series, days, precision=2):
    """NumPy 배열에서 마지막 'days'만큼의 데이터를 추출하고 JSON용으로 포맷팅합니다."""
    # 배열의 마지막 'days' 만큼 슬라이싱
    sliced_series = series[-days:]
    
    # NaN 값을 None으로 바꾸고 소수점 정리
    cleaned_list = []
    for item in sliced_series:
        if np.isnan(item):
            cleaned_list.append(None)
        else:
            cleaned_list.append(round(item, precision))
            
    return cleaned_list

def restructure_history(history_data):
    """
    {'dates': [...], 'key1': [...]} 형태의 딕셔너리를
    [{'date': ..., 'key1': ...}] 형태의 리스트로 변환합니다.
    """
    # 딕셔너리의 키들을 리스트로 변환 (예: ['dates', 'macd', 'signal'])
    keys = list(history_data.keys())
    
    # 딕셔너리의 값 리스트들을 묶어서 튜플의 리스트로 변환
    # 예: [('2025-08-14', 150.12, 180.98), ('2025-08-15', 120.56, 160.54)]
    zipped_values = zip(*history_data.values())
    
    # 각 튜플을 다시 딕셔너리로 조립
    # 예: {'dates': '2025-08-14', 'macd': 150.12, 'signal': 180.98}
    restructured_list = [dict(zip(keys, values)) for values in zipped_values]
    
    return restructured_list

def analyze_ma_price(current_price, ma20, proximity_threshold=1.0):
    """방법 1: 현재 주가와 20일 이동평균선의 위치 관계 분석"""
    diff_percent = ((current_price - ma20) / ma20) * 100
    status = ""
    description = ""

    if abs(diff_percent) <= proximity_threshold:
        status = "🚦 횡보 신호"
        description = "현재 주가가 20일 이동평균선에 근접하여, 방향성을 탐색하고 있습니다."
    elif current_price > ma20:
        status = "📈 상승 신호"
        description = "현재 주가는 20일 이동평균선 위에 위치하여, 단기 상승 추세에 있습니다."
    else:
        status = "📉 하락 신호"
        description = "현재 주가는 20일 이동평균선 아래에 위치하여, 단기 하락 추세에 있습니다."
    
    return {"status": status, "description": description}

def analyze_ma_arrangement(ma5, ma20, ma60):
    """방법 2: 이동평균선의 배열 상태 (정배열/역배열) 분석"""
    status = ""
    description = ""

    if ma5 > ma20 and ma20 > ma60:
        status = "📈 정배열 (강력한 상승 추세)"
        description = "현재 단기-중기-장기 이동평균선이 정배열 상태로, 강력한 상승 추세를 보여주고 있습니다."
    elif ma60 > ma20 and ma20 > ma5:
        status = "📉 역배열 (강력한 하락 추세)"
        description = "현재 이동평균선들이 역배열 상태로, 강력한 하락 추세가 진행 중입니다."
    else:
        status = "🚦 혼조세 (방향성 없음)"
        description = "현재 이동평균선들이 혼조세를 보이며, 뚜렷한 방향성 없이 횡보하고 있습니다."
        
    return {"status": status, "description": description}

def analyze_macd(macd_hist):
    """MACD 히스토그램 분석"""
    status = ""
    if macd_hist > 0:
        status = f"현재 MACD 히스토그램은 +{macd_hist:.2f}로, 상승 힘이 우세한 상태입니다."
    else:
        status = f"현재 MACD 히스토그램은 {macd_hist:.2f}로, 하락 힘이 우세한 상태입니다."
        
    return {"value": round(macd_hist, 2), "analysis": status}

def analyze_rsi(rsi):
    """RSI 분석"""
    status = ""
    description = ""
    if rsi > 70:
        status = "🥵 과매수"
        description = f"RSI가 {rsi:.2f}로 70 이상이므로 시장이 과열되었다는 신호입니다. 단기적인 가격 조정 가능성이 있습니다."
    elif rsi < 30:
        status = "🥶 과매도"
        description = f"RSI가 {rsi:.2f}로 30 이하이므로 시장이 침체되었다는 신호입니다. 기술적 반등을 기대해볼 수 있습니다."
    else:
        status = "NEUTRAL 중립"
        description = f"RSI가 {rsi:.2f}로 중립 구간에 있어, 현재는 매수와 매도 힘이 균형을 이루고 있습니다."

    return {"value": round(rsi, 2), "status": status, "analysis": description}

def analyze_stochastic(slowk):
    """Stochastic Oscillator 분석"""
    status = ""
    description = ""
    if slowk > 80:
        status = "🥵 과매수"
        description = f"스토캐스틱(%K) 값이 {slowk:.2f}로 과매수 구간에 진입하여 단기 조정 가능성이 있습니다."
    elif slowk < 20:
        status = "🥶 과매도"
        description = f"스토캐스틱(%K) 값이 {slowk:.2f}로 과매도 구간에 있어 기술적 반등을 기대해볼 수 있습니다."
    else:
        status = "NEUTRAL 중립"
        description = f"스토캐스틱(%K) 값이 {slowk:.2f}로 중립 구간(20~80)에 위치하고 있습니다."

    return {"value": round(slowk, 2), "status": status, "analysis": description}

def analyze_main_data(df: pd.DataFrame, history_days: int = 30):
    """
    주요 기술적 지표를 계산하고, 과거 데이터를 포함하여 분석 결과를 반환합니다. (수정됨)
    """
    if len(df) < 60:
        return {"error": f"데이터가 60일치 미만이라 모든 지표를 분석할 수 없습니다."}

    # ... (TA-Lib 계산을 위한 데이터 준비는 동일) ...
    open_p = df['open'].values.astype('double')
    high_p = df['high'].values.astype('double')
    low_p = df['low'].values.astype('double')
    close_p = df['close'].values.astype('double')

    # 모든 기술적 지표 계산 (동일)
    ma5 = talib.SMA(close_p, timeperiod=5)
    ma20 = talib.SMA(close_p, timeperiod=20)
    ma60 = talib.SMA(close_p, timeperiod=60)
    macd, macd_signal, macd_hist = talib.MACD(close_p, fastperiod=12, slowperiod=26, signalperiod=9)
    rsi = talib.RSI(close_p, timeperiod=14)
    slowk, slowd = talib.STOCH(high_p, low_p, close_p, fastk_period=5, slowk_period=3, slowd_period=3)

    # ... (가장 최신 데이터 추출은 동일) ...
    latest_close = close_p[-1]
    latest_ma5 = ma5[-1]
    latest_ma20 = ma20[-1]
    latest_ma60 = ma60[-1]
    latest_macd_hist = macd_hist[-1]
    latest_rsi = rsi[-1]
    latest_slowk = slowk[-1]

    # 각 지표별 분석 실행 (동일)
    ma_analysis1 = analyze_ma_price(latest_close, latest_ma20)
    ma_analysis2 = analyze_ma_arrangement(latest_ma5, latest_ma20, latest_ma60)
    macd_analysis = analyze_macd(latest_macd_hist)
    rsi_analysis = analyze_rsi(latest_rsi)
    stochastic_analysis = analyze_stochastic(latest_slowk)

    # --- 과거 데이터 추가 ---
    dates = df['date'].dt.strftime('%Y-%m-%d').tolist()[-history_days:]
    
    return {
        "moving_average": {
            "price_vs_ma20": ma_analysis1,
            "arrangement": ma_analysis2,
            "history": restructure_history({
                "date": dates,
                "ma5": format_history(ma5, history_days),
                "ma20": format_history(ma20, history_days),
                "ma60": format_history(ma60, history_days),
            })
        },
        "macd": {
            **macd_analysis,
            "history": restructure_history({
                "date": dates,
                "macd": format_history(macd, history_days, 4),
                "signal": format_history(macd_signal, history_days, 4),
                "histogram": format_history(macd_hist, history_days, 2),
            })
        },
        "rsi": {
            **rsi_analysis,
            "history": restructure_history({
                "date": dates,
                "rsi": format_history(rsi, history_days),
            })
        },
        "stochastic": {
            **stochastic_analysis,
            "history": restructure_history({
                "date": dates,
                "slowk": format_history(slowk, history_days),
                "slowd": format_history(slowd, history_days),
            })
        }
    }

# ---------------------- 변동성 지표 분석 ---------------------- 

def analyze_rvi(rvi_series, signal_series):
    """## 🔋 RVI (Relative Vigor Index) 분석 (수정됨)"""
    rvi1, rvi2 = rvi_series.iloc[-1], rvi_series.iloc[-2]
    sig1, sig2 = signal_series.iloc[-1], signal_series.iloc[-2]

    status = ""
    analysis = ""

    if rvi2 < sig2 and rvi1 > sig1:
        status = "📈 상승 활력 강화"
        analysis = "최근 RVI 선이 시그널 선을 상향 돌파(골든크로스)하여, 상승 추세의 힘이 강해지고 있습니다."
    elif rvi2 > sig2 and rvi1 < sig1:
        status = "📉 하락 활력 강화"
        analysis = "최근 RVI 선이 시그널 선을 하향 돌파(데드크로스)하여, 하락 추세의 힘이 강해지고 있습니다."
    else:
        status = "🚦 활력 교착 상태"
        analysis = "RVI 선과 시그널 선이 얽혀있어, 현재 추세의 방향성이 약해지고 있습니다."
    
    return {
        "status": status,
        "analysis": analysis,
        "value": {"rvi": round(rvi1, 4), "signal": round(sig1, 4)}
    }

def analyze_atr(atr_value, avg_atr_value, current_price):
    """## 📏 ATR (Average True Range) 분석 (수정됨)"""
    support_price = current_price - atr_value
    resistance_price = current_price + atr_value
    
    status_text = "유지"
    if atr_value > avg_atr_value * 1.1:
        status_text = "확대"
    elif atr_value < avg_atr_value * 0.9:
        status_text = "축소"

    analysis = (
        f"현재 ATR은 {atr_value:,.0f}원으로, 하루 평균 약 {atr_value:,.0f}원 범위의 변동성을 보입니다. "
        f"이는 과거 평균 대비 변동성이 {status_text}된 상태이며, "
        f"단기 지지/저항선은 약 {support_price:,.0f}원 ~ {resistance_price:,.0f}원으로 예상됩니다."
    )
    
    return {
        "status": f"📊 변동성 {status_text}",
        "analysis": analysis,
        "value": {
            "atr": f"{atr_value:,.0f}",
            "avg_atr": f"{avg_atr_value:,.0f}"
        }
    }

def analyze_volatility(vol_value, avg_vol_value):
    """## 🌋 변동폭 (Standard Deviation) 분석 (수정됨)"""
    status_text = "평균 수준"
    if vol_value > avg_vol_value * 1.2:
        status_text = "높은 수준"
    elif vol_value < avg_vol_value * 0.8:
        status_text = "낮은 수준(에너지 응축)"
        
    analysis = (
        f"현재 변동성은 {vol_value:.2f}%로, 과거 평균({avg_vol_value:.2f}%) 대비 {status_text}입니다. "
        f"{status_text}의 변동성은 단기적으로 큰 가격 변동 가능성을 의미할 수 있습니다."
    )
        
    return {
        "status": f"🔥 에너지 {status_text}",
        "analysis": analysis,
        "value": {
            "volatility_percent": round(vol_value, 2),
            "avg_volatility_percent": round(avg_vol_value, 2)
        }
    }

def analyze_volatility_data(df: pd.DataFrame, history_days: int = 30):
    """
    변동성 지표를 계산하고, 과거 데이터를 포함하여 분석 결과를 반환합니다. (수정됨)
    """
    if len(df) < 50:
        return {"error": "데이터가 50일치 미만이라 변동성 평균을 분석할 수 없습니다."}

    rvi_num = (df['close'] - df['open']).rolling(window=10).mean()
    rvi_den = (df['high'] - df['low']).rolling(window=10).mean()
    df['rvi'] = rvi_num / rvi_den
    df['rvi_signal'] = df['rvi'].rolling(window=4).mean()
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    df['volatility'] = df['close'].pct_change().rolling(window=10).std() * 100

    df.dropna(inplace=True)
    if len(df) < 2:
        return {"error": "지표 계산 후 분석할 데이터가 부족합니다."}
    
    latest = df.iloc[-1]
    latest_price = latest['close']
    avg_atr = df['atr'].rolling(window=50).mean().iloc[-1]
    avg_vol = df['volatility'].rolling(window=50).mean().iloc[-1]

    # 각 지표별 분석 실행 (동일)
    rvi_analysis = analyze_rvi(df['rvi'], df['rvi_signal'])
    atr_analysis = analyze_atr(latest['atr'], avg_atr, latest_price)
    volatility_analysis = analyze_volatility(latest['volatility'], avg_vol)

    # --- 과거 데이터 추가 ---
    dates = df['date'].dt.strftime('%Y-%m-%d').tolist()[-history_days:]

    return {
        "rvi": {
            **rvi_analysis,
            "history": restructure_history({
                "dates": dates,
                "rvi": format_history(df['rvi'].values, history_days, 4),
                "signal": format_history(df['rvi_signal'].values, history_days, 4),
            })
        },
        "atr": {
            **atr_analysis,
            "history": restructure_history({
                "dates": dates,
                "atr": format_history(df['atr'].values, history_days, 0),
            })
        },
        "volatility": {
            **volatility_analysis,
            "history": restructure_history({
                "dates": dates,
                "volatility": format_history(df['volatility'].values, history_days, 2),
            })
        }
    }

# ---------------------- 거래량 지표 분석 ---------------------- 

def analyze_mfi(mfi_value):
    """## 💰 MFI (Money Flow Index) 분석"""
    status, analysis = "", ""
    if mfi_value > 80:
        status = "🥵 과매수 신호"
        analysis = f"MFI가 {mfi_value:.2f}로, 시장에 자금이 과도하게 유입되어 단기 과열 상태입니다. 차익 실현 매물에 주의가 필요합니다."
    elif mfi_value < 20:
        status = "🥶 과매도 신호"
        analysis = f"MFI가 {mfi_value:.2f}로, 자금 유출이 과도하여 시장이 침체되었습니다. 저가 매수세 유입 가능성이 있습니다."
    else:
        status = "🚦 중립 상태"
        analysis = f"MFI가 {mfi_value:.2f}로, 자금 유입과 유출이 균형을 이루고 있습니다."
    
    return {"status": status, "analysis": analysis, "value": round(mfi_value, 2)}

def analyze_obv(obv_series):
    """## 👉 OBV (On Balance Volume) 분석"""
    obv_ma = obv_series.rolling(window=20).mean()
    latest_obv = obv_series.iloc[-1]
    latest_obv_ma = obv_ma.iloc[-1]
    
    status, analysis = "", ""
    if latest_obv > latest_obv_ma:
        status = "📈 매집 추세"
        analysis = "OBV가 OBV 이동평균선 위에 위치하여, 주가 상승일에 거래량이 많아 매집 에너지가 축적되고 있을 가능성이 높습니다."
    else:
        status = "📉 분산 추세"
        analysis = "OBV가 OBV 이동평균선 아래에 위치하여, 주가 하락일에 거래량이 많아 매도 압력이 더 강한 것으로 보입니다."
        
    return {"status": status, "analysis": analysis, "value": {"obv": f"{latest_obv:,.0f}", "obv_ma20": f"{latest_obv_ma:,.0f}"}}

def analyze_volume(current_volume, avg_volume):
    """## 📊 현재 거래량 및 평균 거래량 분석"""
    volume_ratio = (current_volume / avg_volume) * 100
    status_text = ""
    
    if volume_ratio > 150:
        status_text = f"급증 (평균 대비 {volume_ratio:.0f}%)"
    elif volume_ratio > 110:
        status_text = f"증가 (평균 대비 {volume_ratio:.0f}%)"
    elif volume_ratio < 90:
        status_text = f"감소 (평균 대비 {volume_ratio:.0f}%)"
    else:
        status_text = f"유지 (평균 대비 {volume_ratio:.0f}%)"

    analysis = (
        f"현재 거래량은 {current_volume:,.0f}주로, 최근 20일 평균 거래량({avg_volume:,.0f}주) 대비 {status_text} 상태입니다. "
        "거래량의 변화는 주가 추세의 신뢰도를 판단하는 중요한 기준이 됩니다."
    )
    
    return {
        "status": f"📊 관심도 {status_text.split(' ')[0]}",
        "analysis": analysis,
        "value": {"volume": f"{current_volume:,.0f}", "avg_volume_20": f"{avg_volume:,.0f}"}
    }

def analyze_volume_data(df: pd.DataFrame, history_days: int = 30):
    """
    주가 데이터 DataFrame을 받아 거래량 지표를 계산하고 분석 결과를 반환합니다.
    """
    if len(df) < 20: # 20일 평균 거래량 계산을 위해 최소 20일 필요
        return {"error": "데이터가 20일치 미만이라 거래량 지표를 분석할 수 없습니다."}

    # 지표 계산
    df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
    df['obv'] = talib.OBV(df['close'], df['volume'])
    df['avg_volume_20'] = df['volume'].rolling(window=20).mean()

    # 데이터 정제
    df.dropna(inplace=True)
    if len(df) < 1:
        return {"error": "지표 계산 후 분석할 데이터가 부족합니다."}

    # 최신 데이터 추출
    latest = df.iloc[-1]
    dates = df['date'].dt.strftime('%Y-%m-%d').tolist()[-history_days:]

    # 분석 함수 호출
    mfi_analysis = analyze_mfi(latest['mfi'])
    obv_analysis = analyze_obv(df['obv'])
    volume_analysis = analyze_volume(latest['volume'], latest['avg_volume_20'])

    # 최종 결과 조합
    return {
        "mfi": {
            **mfi_analysis,
            "history": restructure_history({
                "date": dates,
                "mfi": format_history(df['mfi'].values, history_days)
            })
        },
        "obv": {
            **obv_analysis,
            "history": restructure_history({
                "date": dates,
                "obv": format_history(df['obv'].values, history_days, 0)
            })
        },
        "volume": {
            **volume_analysis,
            "history": restructure_history({
                "date": dates,
                "volume": format_history(df['volume'].values, history_days, 0),
                "avg_volume_20": format_history(df['avg_volume_20'].values, history_days, 0)
            })
        }
    }



















financial_df = fetch_stock_data(stock_collection, "005930")

result1 = analyze_main_data(financial_df.copy())
pprint(result1)
print("---------------------------------------------------")
result2 = analyze_volatility_data(financial_df.copy())
pprint(result2)
print("---------------------------------------------------")
result3 = analyze_volume_data(financial_df.copy())
pprint(result3)
print("---------------------------------------------------")
result4 = get_financial_data("005930")
pprint(result4)
