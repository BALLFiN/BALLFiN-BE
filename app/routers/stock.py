from fastapi import APIRouter, Query, HTTPException, Path, Depends
from pymongo import DESCENDING, ASCENDING
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from app.db.mongo import stock_collection, user_collection
from app.core.security import get_current_user

router = APIRouter(tags=["Stock"])

@router.get(
    "/search",
    summary="주가 데이터 검색",
    description="""
    종목코드별로 최근 N개의 캔들 데이터를 조회합니다.

    - stock_codes: 검색할 종목코드들 (콤마로 구분, 예: "005930,000660")
    - period: D(일봉 N일), W(주봉 N주), M(월봉 N개월)
    - count: 조회할 개수 (기본 30개)
    - sort_by: newest(최신순), oldest(오래된순), volume(거래량순)
    """
)
def search_stock_data(
    stock_codes: str = Query(..., description="종목코드 (콤마로 구분, 예: 005930,000660)"),
    period: str = Query("D", description="D(일봉) | W(주봉) | M(월봉)"),
    count: int = Query(30, description="조회할 개수", ge=1, le=500),
    sort_by: str = Query("newest", description="newest | oldest | volume")
):
    if period not in ["D", "W", "M"]:
        raise HTTPException(status_code=400, detail="period는 D, W, M 중 하나여야 합니다.")

    # 종목코드 파싱
    code_list = [code.strip() for code in stock_codes.split(",")]
    
    results = {}
    
    for stock_code in code_list:
        query = {"stock_code": stock_code, "period": period}
        
        # 정렬 옵션
        if sort_by == "oldest":
            sort_option = [("date", ASCENDING)]
        elif sort_by == "volume":
            sort_option = [("volume", DESCENDING), ("date", DESCENDING)]
        else:  # newest (기본값)
            sort_option = [("date", DESCENDING)]
        
        # 데이터 조회
        cursor = stock_collection.find(query).sort(sort_option).limit(count)
        data_list = list(cursor)
        
        if not data_list:
            results[stock_code] = {"error": "데이터 없음"}
            continue
        
        
        # 응답 데이터 구성
        candles = []
        for doc in data_list:
            candles.append({
                "date": doc["date"].strftime("%Y-%m-%d"),
                "open": doc["open"],
                "high": doc["high"], 
                "low": doc["low"],
                "close": doc["close"],
                "volume": doc["volume"]
            })
        
        # 변화율 계산 (첫날 대비 마지막날)
        change = None
        change_rate = None
        if len(candles) > 1:
            first_price = candles[0]["close"]
            last_price = candles[-1]["close"]
            change = last_price - first_price
            change_rate = round((change / first_price) * 100, 2)
        
        results[stock_code] = {
            "period": period,
            "count": len(candles),
            "candles": candles,
            "summary": {
                "first_date": candles[0]["date"] if candles else None,
                "last_date": candles[-1]["date"] if candles else None,
                "first_price": candles[0]["close"] if candles else None,
                "last_price": candles[-1]["close"] if candles else None,
                "change": change,
                "change_rate": change_rate,
                "max_price": max(c["high"] for c in candles) if candles else None,
                "min_price": min(c["low"] for c in candles) if candles else None,
                "avg_volume": round(sum(c["volume"] for c in candles) / len(candles)) if candles else None
            }
        }
    
    return {
        "period": period,
        "requested_count": count,
        "sort_by": sort_by,
        "stocks": results
    }

@router.get(
    "/chart/{stock_code}",
    summary="개별 종목 차트 데이터",
    description="""
    특정 종목의 최근 N개 캔들 데이터를 조회합니다.
    
    - stock_code: 종목코드
    - period: D(일봉 N일), W(주봉 N주), M(월봉 N개월)  
    - count: 조회할 개수
    """
)
def get_stock_chart(
    stock_code: str = Path(..., description="종목코드 (예: 005930)"),
    period: str = Query("D", description="D(일봉) | W(주봉) | M(월봉)"),
    count: int = Query(30, description="조회할 개수", ge=1, le=500)
):
    if period not in ["D", "W", "M"]:
        raise HTTPException(status_code=400, detail="period는 D, W, M 중 하나여야 합니다.")

    query = {"stock_code": stock_code, "period": period}
    
    # 최신 데이터부터 조회 후 시계열 순으로 정렬
    cursor = stock_collection.find(query).sort("date", DESCENDING).limit(count)
    data_list = list(cursor)
    
    if not data_list:
        raise HTTPException(status_code=404, detail=f"종목 {stock_code}의 {period}봉 데이터를 찾을 수 없습니다.")
    
    # 시계열 순으로 정렬
    data_list.reverse()
    
    candles = []
    for doc in data_list:
        candles.append({
            "date": doc["date"].strftime("%Y-%m-%d"),
            "open": doc["open"],
            "high": doc["high"],
            "low": doc["low"], 
            "close": doc["close"],
            "volume": doc["volume"]
        })
    
    # 기간별 변화율 계산
    period_change = None
    period_change_rate = None
    if len(candles) > 1:
        first_price = candles[0]["close"]
        last_price = candles[-1]["close"]
        period_change = last_price - first_price
        period_change_rate = round((period_change / first_price) * 100, 2)
    
    # 전일/전주/전월 대비 계산
    recent_change = None
    recent_change_rate = None
    if len(candles) > 1:
        prev_price = candles[-2]["close"]
        current_price = candles[-1]["close"]
        recent_change = current_price - prev_price
        recent_change_rate = round((recent_change / prev_price) * 100, 2)
    
    return {
        "stock_code": stock_code,
        "period": period,
        "count": len(candles),
        "candles": candles,
        "summary": {
            "period_name": {"D": "일봉", "W": "주봉", "M": "월봉"}[period],
            "first_date": candles[0]["date"],
            "last_date": candles[-1]["date"],
            "current_price": candles[-1]["close"],
            "period_change": period_change,
            "period_change_rate": period_change_rate,
            "recent_change": recent_change,
            "recent_change_rate": recent_change_rate,
            "highest": max(c["high"] for c in candles),
            "lowest": min(c["low"] for c in candles),
            "avg_volume": round(sum(c["volume"] for c in candles) / len(candles))
        }
    }

@router.get(
    "/latest/{stock_code}",
    summary="종목 최신 가격 (모든 기간)",
    description="""
    특정 종목의 일봉/주봉/월봉 최신 가격을 한 번에 조회합니다.
    """
)
def get_latest_prices(
    stock_code: str = Path(..., description="종목코드 (예: 005930)")
):
    results = {}
    
    for period in ["D", "W", "M"]:
        # 최신 2개 데이터 조회 (변화율 계산용)
        cursor = stock_collection.find(
            {"stock_code": stock_code, "period": period}
        ).sort("date", DESCENDING).limit(2)
        
        data_list = list(cursor)
        
        if not data_list:
            results[period] = None
            continue
        
        latest = data_list[0]
        previous = data_list[1] if len(data_list) > 1 else None
        
        result = {
            "date": latest["date"].strftime("%Y-%m-%d"),
            "open": latest["open"],
            "high": latest["high"],
            "low": latest["low"],
            "close": latest["close"],
            "volume": latest["volume"],
            "change": None,
            "change_rate": None
        }
        
        # 변화율 계산
        if previous:
            change = latest["close"] - previous["close"]
            change_rate = round((change / previous["close"]) * 100, 2)
            result["change"] = change
            result["change_rate"] = change_rate
        
        results[period] = result
    
    if not any(results.values()):
        raise HTTPException(status_code=404, detail=f"종목 {stock_code}의 데이터를 찾을 수 없습니다.")
    
    return {
        "stock_code": stock_code,
        "daily": results["D"],
        "weekly": results["W"],
        "monthly": results["M"],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@router.get(
    "/my-portfolio",
    summary="사용자 즐겨찾기 포트폴리오",
    description="""
    사용자의 즐겨찾기 종목들의 최근 N개 데이터를 조회합니다.
    """
)
def get_user_portfolio(
    current_user: str = Depends(get_current_user),
    period: str = Query("D", description="D(일봉) | W(주봉) | M(월봉)"),
    count: int = Query(1, description="각 종목별 조회할 개수", ge=1, le=100)
):
    # 사용자 즐겨찾기 조회
    user = user_collection.find_one({"email": current_user})
    if not user or "favorites" not in user or not user["favorites"]:
        return {"message": "즐겨찾기 종목이 없습니다.", "stocks": []}
    
    favorite_stocks = user["favorites"]
    results = []
    
    for stock_code in favorite_stocks:
        query = {"stock_code": stock_code, "period": period}
        
        # 최신 count개 조회
        cursor = stock_collection.find(query).sort("date", DESCENDING).limit(count)
        data_list = list(cursor)
        
        if not data_list:
            continue
        
        # 변화율 계산 (count > 1인 경우 기간 변화율, count = 1인 경우 전일 대비)
        if count == 1:
            # 전일 대비 계산을 위해 이전 데이터 1개 더 조회
            prev_doc = stock_collection.find_one(
                {"stock_code": stock_code, "period": period, "date": {"$lt": data_list[0]["date"]}},
                sort=[("date", DESCENDING)]
            )
            
            change = None
            change_rate = None
            if prev_doc:
                change = data_list[0]["close"] - prev_doc["close"]
                change_rate = round((change / prev_doc["close"]) * 100, 2)
            
            results.append({
                "stock_code": stock_code,
                "date": data_list[0]["date"].strftime("%Y-%m-%d"),
                "close": data_list[0]["close"],
                "volume": data_list[0]["volume"],
                "change": change,
                "change_rate": change_rate
            })
        else:
            # 기간 변화율 계산
            data_list.reverse()  # 시계열 순으로 정렬
            
            first_price = data_list[0]["close"]
            last_price = data_list[-1]["close"]
            period_change = last_price - first_price
            period_change_rate = round((period_change / first_price) * 100, 2)
            
            results.append({
                "stock_code": stock_code,
                "period_start": data_list[0]["date"].strftime("%Y-%m-%d"),
                "period_end": data_list[-1]["date"].strftime("%Y-%m-%d"),
                "start_price": first_price,
                "end_price": last_price,
                "period_change": period_change,
                "period_change_rate": period_change_rate,
                "count": len(data_list)
            })
    
    # 변화율 기준으로 정렬
    if count == 1:
        results.sort(key=lambda x: x["change_rate"] or -999, reverse=True)
    else:
        results.sort(key=lambda x: x["period_change_rate"], reverse=True)
    
    return {
        "user": current_user,
        "period": period,
        "count": count,
        "total_stocks": len(results),
        "stocks": results
    }

@router.get(
    "/compare",
    summary="종목 비교",
    description="""
    여러 종목의 최근 N개 데이터를 비교합니다.
    """
)
def compare_stocks(
    stock_codes: str = Query(..., description="비교할 종목코드들 (콤마로 구분)"),
    period: str = Query("D", description="D(일봉) | W(주봉) | M(월봉)"),
    count: int = Query(30, description="비교 기간", ge=1, le=200)
):
    if period not in ["D", "W", "M"]:
        raise HTTPException(status_code=400, detail="period는 D, W, M 중 하나여야 합니다.")
    
    code_list = [code.strip() for code in stock_codes.split(",")]
    
    if len(code_list) > 10:
        raise HTTPException(status_code=400, detail="최대 10개 종목까지 비교 가능합니다.")
    
    comparison_data = []
    
    for stock_code in code_list:
        query = {"stock_code": stock_code, "period": period}
        
        cursor = stock_collection.find(query).sort("date", DESCENDING).limit(count)
        data_list = list(cursor)
        
        if not data_list:
            comparison_data.append({
                "stock_code": stock_code,
                "error": "데이터 없음"
            })
            continue
        
        data_list.reverse()  # 시계열 순으로 정렬
        
        # 수익률 계산
        first_price = data_list[0]["close"]
        last_price = data_list[-1]["close"]
        total_return = round(((last_price - first_price) / first_price) * 100, 2)
        
        # 변동성 계산
        prices = [doc["close"] for doc in data_list]
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        avg_return = sum(returns) / len(returns)
        volatility = round((sum((r - avg_return)**2 for r in returns) / len(returns))**0.5 * 100, 2)
        
        comparison_data.append({
            "stock_code": stock_code,
            "period_start": data_list[0]["date"].strftime("%Y-%m-%d"),
            "period_end": data_list[-1]["date"].strftime("%Y-%m-%d"),
            "start_price": first_price,
            "end_price": last_price,
            "total_return": total_return,
            "volatility": volatility,
            "max_price": max(doc["high"] for doc in data_list),
            "min_price": min(doc["low"] for doc in data_list),
            "avg_volume": round(sum(doc["volume"] for doc in data_list) / len(data_list)),
            "data_count": len(data_list)
        })
    
    # 수익률 기준으로 정렬
    valid_data = [d for d in comparison_data if "error" not in d]
    valid_data.sort(key=lambda x: x["total_return"], reverse=True)
    
    return {
        "period": period,
        "count": count,
        "comparison": comparison_data,
        "ranking": valid_data
    }

@router.get(
    "/market-overview",
    summary="시장 전체 현황",
    description="""
    수집된 모든 종목의 최신 현황을 요약합니다.
    """
)
def get_market_overview(
    period: str = Query("D", description="D(일봉) | W(주봉) | M(월봉)"),
    top_count: int = Query(5, description="상위 몇 개까지 표시할지", ge=3, le=20)
):
    # 모든 종목의 최신 데이터 조회
    pipeline = [
        {"$match": {"period": period}},
        {"$sort": {"stock_code": 1, "date": -1}},
        {"$group": {
            "_id": "$stock_code",
            "latest": {"$first": "$$ROOT"}
        }}
    ]
    
    latest_data = list(stock_collection.aggregate(pipeline))
    
    if not latest_data:
        return {"message": f"{period}봉 데이터가 없습니다."}
    
    # 각 종목별 변화율 계산
    market_data = []
    for item in latest_data:
        stock_code = item["_id"]
        latest_doc = item["latest"]
        
        # 이전 데이터 조회
        prev_doc = stock_collection.find_one(
            {"stock_code": stock_code, "period": period, "date": {"$lt": latest_doc["date"]}},
            sort=[("date", DESCENDING)]
        )
        
        if prev_doc:
            change = latest_doc["close"] - prev_doc["close"]
            change_rate = round((change / prev_doc["close"]) * 100, 2)
            
            market_data.append({
                "stock_code": stock_code,
                "close": latest_doc["close"],
                "volume": latest_doc["volume"],
                "change": change,
                "change_rate": change_rate,
                "date": latest_doc["date"].strftime("%Y-%m-%d")
            })
    
    if not market_data:
        return {"message": "변화율 계산 가능한 데이터가 없습니다."}
    
    # 통계 계산
    rising = [d for d in market_data if d["change_rate"] > 0]
    falling = [d for d in market_data if d["change_rate"] < 0]
    unchanged = [d for d in market_data if d["change_rate"] == 0]
    
    avg_change = round(sum(d["change_rate"] for d in market_data) / len(market_data), 2)
    
    # 상위/하위 종목
    top_gainers = sorted(market_data, key=lambda x: x["change_rate"], reverse=True)[:top_count]
    top_losers = sorted(market_data, key=lambda x: x["change_rate"])[:top_count]
    top_volume = sorted(market_data, key=lambda x: x["volume"], reverse=True)[:top_count]
    
    return {
        "period": period,
        "market_summary": {
            "total_stocks": len(market_data),
            "rising_stocks": len(rising),
            "falling_stocks": len(falling),
            "unchanged_stocks": len(unchanged),
            "average_change_rate": avg_change
        },
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "top_volume": top_volume,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }