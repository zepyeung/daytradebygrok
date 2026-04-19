import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime

# ====================== Telegram 設定 ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_to_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram Token 或 Chat ID 未設定")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url, 
            json={
                "chat_id": TELEGRAM_CHAT_ID, 
                "text": message, 
                "parse_mode": "HTML"
            }, 
            timeout=15
        )
        if response.status_code == 200:
            print("✅ Telegram 推送成功")
            return True
        else:
            print(f"❌ Telegram 推送失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 推送異常: {e}")
        return False

# ====================== 技術指標 ======================
def calculate_atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

# ====================== 主程式 ======================
tickers = [
    "NVDA", "TSLA", "AAPL", "AMD", "SMCI", "ARM", "PLTR", "META", 
    "GOOGL", "AMZN", "MSFT", "HOOD", "COIN", "MARA", "RIOT", 
    "SOFI", "RIVN", "LCID"
]

now = datetime.now()
now_str = now.strftime('%Y-%m-%d %H:%M ET')

# 週末跳過
if now.weekday() >= 5:
    print(f"[{now_str}] 週末，不執行掃描")
    exit()

print(f"[{now_str}] daytrade_auto.py 開始執行 - 開市後掃描")

results = []

for ticker in tickers:
    try:
        # 使用較長 period 確保有足夠數據計算 RVOL
        data = yf.download(ticker, period="5d", interval="1m", prepost=True)
        
        if data.empty or len(data) < 50:
            continue

        # 計算指標
        data['RVOL'] = data['Volume'] / data['Volume'].rolling(window=20).mean()
        data['ATR'] = calculate_atr(data['High'], data['Low'], data['Close'])

        latest = data.iloc[-1]
        prev = data.iloc[-2]

        change_pct = (latest['Close'] - prev['Close']) / prev['Close'] * 100
        rvol = latest.get('RVOL', 1.0)

        # v3.0 掃描條件（與 Streamlit App 一致）
        if abs(change_pct) >= 2.5 and rvol >= 2.0:
            score = rvol * abs(change_pct) * 1.1
            
            results.append({
                'Ticker': ticker,
                'Price': round(latest['Close'], 2),
                'Change%': round(change_pct, 2),
                'RVOL': round(rvol, 1),
                'Score': round(score, 2),
                'ATR': round(latest['ATR'], 2)
            })
            
    except Exception as e:
        print(f"處理 {ticker} 時出錯: {e}")
        continue

# ====================== 推送結果 ======================
if results:
    df = pd.DataFrame(results).nlargest(5, 'Score')
    
    msg = f"""<b>🚀 v3.0 開市後掃描 Top5</b>
時間：{now_str}
條件：漲跌 ≥2.5% | RVOL ≥2.0x

"""
    
    for _, row in df.iterrows():
        msg += f"📌 <b>{row['Ticker']}</b> | ${row['Price']} | 漲跌 {row['Change%']}% | RVOL {row['RVOL']}x | Score {row['Score']}\n"
        msg += f"ATR: ${row['ATR']}\n\n"
    
    msg += "⚠️ 僅供參考，高風險交易請嚴格止損\n"
    msg += "📈 建議搭配 StockTrade Web App v3.0 查看 AI 目標價"

    send_to_telegram(msg)
    print(f"✅ 已成功推送 {len(df)} 支股票")

else:
    msg = f"""<b>🚀 v3.0 開市後掃描</b>
時間：{now_str}
條件：漲跌 ≥2.5% | RVOL ≥2.0x

今日暫無符合條件的股票。
"""
    send_to_telegram(msg)
    print("ℹ️ 今日無符合股票，已推送空結果")

print(f"[{now_str}] daytrade_auto.py 執行完成")
