import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

TELEGRAM_TOKEN = "8745780257:AAFkzTq8P-qxVu785l0kKiJ-yiAw2SaC8Bc"
TELEGRAM_CHAT_ID = "363146569"

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

now = datetime.now()
if now.weekday() >= 5:
    print("週末，不推送 Pre-Market")
    exit()

print(f"Pre-Market 固定掃描開始 - {now.strftime('%H:%M ET')}")

results = []
for ticker in tickers:
    try:
        data = yf.download(ticker, period="5d", interval="1m", prepost=True)
        if data.empty or len(data) < 30: continue
        
        data['RVOL'] = data['Volume'] / data['Volume'].rolling(20).mean()
        data['ATR'] = calculate_atr(data['High'], data['Low'], data['Close'])
        
        latest = data.iloc[-1]
        change_pct = (latest['Close'] - data.iloc[-2]['Close']) / data.iloc[-2]['Close'] * 100
        rvol = latest.get('RVOL', 1)
        
        if abs(change_pct) >= 3.0 and rvol >= 2.5:
            score = rvol * abs(change_pct) * 1.2
            results.append({
                'Ticker': ticker, 
                'Price': round(latest['Close'],2),
                'Gap%': round(change_pct,2), 
                'RVOL': round(rvol,1),
                'Score': round(score,2)
            })
    except:
        continue

if results:
    df = pd.DataFrame(results).nlargest(5, 'Score')
    msg = f"<b>🚀 Pre-Market 固定推送 Top5</b>\n時間：{now.strftime('%Y-%m-%d %H:%M ET')} | 開市前30分鐘\nGap≥3.0% | RVOL≥2.5x\n\n"
    
    for _, row in df.iterrows():
        msg += f"📌 <b>{row['Ticker']}</b> | ${row['Price']} | Gap {row['Gap%']}% | RVOL {row['RVOL']}x\n"
        msg += "📈 期權推介：高IV環境，建議 Long Straddle / Strangle（買波動）\n⚠️ 期權風險極高\n\n"
    
    send_to_telegram(msg)
    print(f"已推送 {len(df)} 支 Pre-Market 股票")
else:
    print("今日 Pre-Market 無符合股票，不推送")
