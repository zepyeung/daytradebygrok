import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

# 手寫指標（簡化版）
def calculate_atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

# 主要掃描邏輯
tickers = ["NVDA","TSLA","AAPL","AMD","SMCI","ARM","PLTR","META","GOOGL","AMZN","MSFT","HOOD","COIN","MARA","RIOT","SOFI","RIVN","LCID"]
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
        
        if abs(change_pct) >= 4.0 and rvol >= 3.0:
            score = rvol * abs(change_pct) * 1.1
            results.append({
                'Ticker': ticker, 'Price': round(latest['Close'],2),
                'Gap%': round(change_pct,2), 'RVOL': round(rvol,1),
                'Score': round(score,2), 'ATR': round(latest['ATR'],2)
            })
    except:
        continue

if results:
    df = pd.DataFrame(results).nlargest(5, 'Score')
    msg = f"<b>🚀 StockTrade Pre-Market Top5 (自動)</b>\n時間：{datetime.now().strftime('%Y-%m-%d %H:%M ET')}\nGap≥4% | RVOL≥3.0x\n\n"
    
    for _, row in df.iterrows():
        msg += f"📌 <b>{row['Ticker']}</b> | ${row['Price']} | Gap {row['Gap%']}% | RVOL {row['RVOL']}x\n"
        option_note = "高IV環境，建議：Long Straddle/Strangle（買波動）或 Credit Spread\n⚠️ 期權風險極高"
        msg += f"📈 期權推介：{option_note}\n\n"
    
    send_to_telegram(msg)
    print("推送成功")
else:
    send_to_telegram("今日 Pre-Market 暫無符合 Gap≥4% + RVOL≥3.0 的股票。")
    print("無符合股票")
