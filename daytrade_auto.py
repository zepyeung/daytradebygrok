import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

def calculate_atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

tickers = ["NVDA","TSLA","AAPL","AMD","SMCI","ARM","PLTR","META","GOOGL","AMZN","MSFT","HOOD","COIN","MARA","RIOT","SOFI","RIVN","LCID"]

print("開市後每60秒自動掃描已啟動...")

for i in range(60):   # 開市後跑60次（即約1小時），夠用
    now = datetime.now()
    print(f"掃描時間: {now.strftime('%H:%M:%S')}")

    results = []
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="2d", interval="1m", prepost=True)
            if data.empty or len(data) < 30: continue

            data['RVOL'] = data['Volume'] / data['Volume'].rolling(20).mean()
            data['ATR'] = calculate_atr(data['High'], data['Low'], data['Close'])

            latest = data.iloc[-1]
            change_pct = (latest['Close'] - data.iloc[-2]['Close']) / data.iloc[-2]['Close'] * 100
            rvol = latest.get('RVOL', 1)

            if abs(change_pct) >= 4.0 and rvol >= 3.0:
                score = rvol * abs(change_pct) * 1.1
                results.append({
                    'Ticker': ticker, 'Price': round(latest['Close'],2),
                    'Change%': round(change_pct,2), 'RVOL': round(rvol,1),
                    'Score': round(score,2), 'ATR': round(latest['ATR'],2)
                })
        except:
            continue

    if results:
        df = pd.DataFrame(results).nlargest(5, 'Score')
        msg = f"<b>🚀 開市後即時掃描 Top5</b>\n時間：{now.strftime('%H:%M ET')}\n有搵到股票！\n\n"
        for _, row in df.iterrows():
            msg += f"📌 <b>{row['Ticker']}</b> | ${row['Price']} | 漲跌 {row['Change%']}% | RVOL {row['RVOL']}x\n"
            option_note = "高波動，建議 Long Straddle/Strangle（買波動）或小心操作\n⚠️ 期權風險極高"
            msg += f"📈 期權推介：{option_note}\n\n"

        send_to_telegram(msg)
        print(f"已推送 {len(df)} 支股票到 Telegram")
    else:
        print("今次掃描無符合條件股票，唔推送")

    time.sleep(60)   # 每60秒掃一次

print("今日掃描結束")
