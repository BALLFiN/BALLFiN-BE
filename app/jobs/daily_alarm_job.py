from datetime import datetime, timedelta
from pymongo import ASCENDING
import pandas as pd
import numpy as np
from app.db.mongo import stock_collection, user_collection, alarm_collection, company_collection

# ================================
# ⚙️ 기본 설정
# ================================
TICKERS = [
    '207940', '000270', '068270', '035420', '138040', '011200', '051910', '032830',
    '010130', '030200', '267260', '066570', '047050', '047810', '272210', '079550',
    '006800', '021240', '032640', '071050', '028050', '001040', '277810', '005930',
    '373220', '005380', '028260', '086790', '316140', '024110', '064350', '003670',
    '034730', '018260', '326030', '443060', '267250', '010120', '051900', '161390',
    '271560', '029780', '000720', '005940', '298040', '034220', '450080', '377300',
    '009830', '006260', '251270', '247540', '086520', '012450', '105560', '329180',
    '055550', '012330', '042660', '005490', '000810', '096770', '015760', '034020',
    '010140', '006400', '017670', '352820', '000100', '090430', '010950', '180640',
    '088980', '010620', '000150', '016360', '011790', '097950', '196170', '028300',
    '000660', '259960', '035720', '009540', '033780', '402340', '323410', '003550',
    '009150', '086280', '003490', '003230', '042700', '005830', '022100', '078930'
]

# ================================
# 📊 기술적 신호 계산 함수
# ================================
def calculate_signals(df: pd.DataFrame):
    df = df.sort_values("date")

    for w in [5, 20, 60, 120]:
        df[f"ma{w}"] = df["close"].rolling(w).mean()

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    delta = df["close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(14).mean()
    avg_loss = pd.Series(loss).rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    df["price_volatility"] = abs(df["close"].pct_change()) * 100
    return df


# ================================
# 🧠 회사명 캐싱 (성능 개선)
# ================================
def build_company_name_map():
    mapping = {}
    for c in company_collection.find({}, {"stock_code": 1, "corp_name": 1}):
        mapping[c["stock_code"]] = c.get("corp_name", c["stock_code"])
    return mapping


# ================================
# 🚀 스케줄러용 일일 알람 생성 함수
# ================================
def run_daily_alarm_job(target_date: datetime = None):
    target_date = target_date or datetime.now().date()
    print(f"📆 [{target_date}] 일일 알람 계산 시작")

    has_data = stock_collection.find_one({
        "period": "D",
        "date": {"$gte": datetime(target_date.year, target_date.month, target_date.day)}
    })
    if not has_data:
        print("❌ 오늘 날짜의 일봉 데이터가 없습니다. 알람 생성하지 않음.")
        return

    company_map = build_company_name_map()

    for code in TICKERS:
        df = pd.DataFrame(list(
            stock_collection.find({"stock_code": code, "period": "D"}).sort("date", ASCENDING)
        ))
        if df.empty:
            continue

        corp_name = company_map.get(code, code)
        display_name = f"{corp_name} ({code})"

        df = calculate_signals(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else None

        triggered_signals = []

        if latest["price_volatility"] >= 10:
            triggered_signals.append(("price_volatility",
                f"💹 {display_name}의 주가가 전일 대비 10% 이상 급변했습니다. 변동성이 확대되고 있습니다."
            ))

        if prev is not None:
            if not (prev["ma5"] > prev["ma20"] > prev["ma60"] > prev["ma120"]) and \
               (latest["ma5"] > latest["ma20"] > latest["ma60"] > latest["ma120"]):
                triggered_signals.append(("golden_cross",
                    f"🌟 {display_name}의 이동평균선이 정배열로 전환되었습니다. 상승 추세 신호로 해석됩니다."
                ))
            if not (prev["ma5"] < prev["ma20"] < prev["ma60"] < prev["ma120"]) and \
               (latest["ma5"] < latest["ma20"] < latest["ma60"] < latest["ma120"]):
                triggered_signals.append(("dead_cross",
                    f"⚠️ {display_name}의 이동평균선이 역배열로 전환되었습니다. 하락 추세 전환 가능성을 유의하세요."
                ))

        if prev is not None:
            if prev["macd"] <= prev["signal"] and latest["macd"] > latest["signal"]:
                triggered_signals.append(("macd_golden",
                    f"📈 {display_name}에서 MACD 골든크로스가 발생했습니다. 단기 상승 모멘텀 신호입니다."
                ))
            if prev["macd"] >= prev["signal"] and latest["macd"] < latest["signal"]:
                triggered_signals.append(("macd_dead",
                    f"📉 {display_name}에서 MACD 데드크로스가 발생했습니다. 단기 조정 신호로 해석됩니다."
                ))

        if prev is not None:
            if prev["rsi"] >= 30 and latest["rsi"] < 30:
                triggered_signals.append(("rsi_low",
                    f"😟 {display_name}의 RSI가 30 이하로 하락했습니다. 과매도 구간 진입 가능성이 있습니다."
                ))
            if prev["rsi"] <= 80 and latest["rsi"] > 80:
                triggered_signals.append(("rsi_high",
                    f"😎 {display_name}의 RSI가 80을 돌파했습니다. 과매수 신호로 단기 조정이 나타날 수 있습니다."
                ))

        for signal_key, message in triggered_signals:
            target_users = list(user_collection.find({
                "favorites": code,
                f"alarm_settings.{signal_key}": True
            }))
            if not target_users:
                continue

            now = datetime.utcnow()
            new_alarms = [{
                "user_id": str(u["_id"]),
                "user_email": u["email"],
                "alarm_type": signal_key,
                "content": message,
                "company": code,
                "read": False,
                "created_at": now,
                "target_path": None,
                "score": None
            } for u in target_users]

            alarm_collection.insert_many(new_alarms)
            print(f"📨 {display_name}: {signal_key} → {len(new_alarms)}명에게 알람 전송")

    print("✅ 일일 알람 계산 완료")


# ================================
# 🕰 과거 1년치 백필용 함수
# ================================
def backfill_alarms_for_year(stock_code="005930", start_date=None):
    print(f"📆 [{stock_code}] 과거 1년치 알람 생성 시작")

    end_date = datetime.now()
    start_date = start_date or (end_date - timedelta(days=365))
    company_map = build_company_name_map()
    corp_name = company_map.get(stock_code, stock_code)
    display_name = f"{corp_name} ({stock_code})"

    df = pd.DataFrame(list(
        stock_collection.find({
            "stock_code": stock_code,
            "period": "D",
            "date": {"$gte": start_date, "$lte": end_date}
        }).sort("date", ASCENDING)
    ))
    if df.empty:
        print("❌ 일봉 데이터가 없습니다.")
        return

    df = calculate_signals(df)
    print(f"✅ 데이터 {len(df)}행 로드됨 ({df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')})")

    users = list(user_collection.find({"favorites": stock_code}))
    if not users:
        print("⚠️ 해당 종목을 관심등록한 유저가 없습니다.")
        return

    inserted = 0
    for i in range(1, len(df)):
        prev, latest = df.iloc[i - 1], df.iloc[i]
        triggered_signals = []

        if latest["price_volatility"] >= 10:
            triggered_signals.append(("price_volatility", f"💹 {display_name}의 주가가 전일 대비 10% 이상 급변했습니다. 변동성이 확대되고 있습니다."))
        if not (prev["ma5"] > prev["ma20"] > prev["ma60"] > prev["ma120"]) and (latest["ma5"] > latest["ma20"] > latest["ma60"] > latest["ma120"]):
            triggered_signals.append(("golden_cross", f"🌟 {display_name}의 이동평균선이 정배열로 전환되었습니다. 상승 추세 신호로 해석됩니다."))
        if not (prev["ma5"] < prev["ma20"] < prev["ma60"] < prev["ma120"]) and (latest["ma5"] < latest["ma20"] < latest["ma60"] < latest["ma120"]):
            triggered_signals.append(("dead_cross", f"⚠️ {display_name}의 이동평균선이 역배열로 전환되었습니다. 하락 추세 전환 가능성을 유의하세요."))
        if prev["macd"] <= prev["signal"] and latest["macd"] > latest["signal"]:
            triggered_signals.append(("macd_golden", f"📈 {display_name}에서 MACD 골든크로스가 발생했습니다. 단기 상승 모멘텀 신호입니다."))
        if prev["macd"] >= prev["signal"] and latest["macd"] < latest["signal"]:
            triggered_signals.append(("macd_dead", f"📉 {display_name}에서 MACD 데드크로스가 발생했습니다. 단기 조정 신호로 해석됩니다."))
        if prev["rsi"] >= 30 and latest["rsi"] < 30:
            triggered_signals.append(("rsi_low", f"😟 {display_name}의 RSI가 30 이하로 하락했습니다. 과매도 구간 진입 가능성이 있습니다."))
        if prev["rsi"] <= 80 and latest["rsi"] > 80:
            triggered_signals.append(("rsi_high", f"😎 {display_name}의 RSI가 80을 돌파했습니다. 과매수 신호로 단기 조정이 나타날 수 있습니다."))

        for signal_key, message in triggered_signals:
            target_users = [u for u in users if u.get("alarm_settings", {}).get(signal_key)]
            if not target_users:
                continue

            new_alarms = [{
                "user_id": str(u["_id"]),
                "user_email": u["email"],
                "alarm_type": signal_key,
                "content": message,
                "company": stock_code,
                "read": False,
                "created_at": latest["date"],
                "target_path": None,
                "score": None
            } for u in target_users]

            alarm_collection.insert_many(new_alarms)
            inserted += len(new_alarms)

    print(f"✅ {inserted}건 알람 생성 완료")
