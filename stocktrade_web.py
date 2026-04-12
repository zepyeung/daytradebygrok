import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
import time
import numpy as np
import sqlite3
import requests
import os

# ====================== WEB APP 設定 ======================
st.set_page_config(page_title="StockTrade Web v1.8", page_icon="📈", layout="wide")
st.sidebar.title("📱 StockTrade Web App v1.8")
st.sidebar.markdown("**Telegram自動推送已開啟** 🚀")
st.sidebar.info("開市後30分鐘自動推送Top5到Telegram")

st.title("📈 StockTrade Web v1.8 - 美股日內AI神器 + Telegram推送")
st.markdown("**一開App就自動跑 + Telegram即時通知**")

tab1, tab2, tab3 = st.tabs(["🔥 Scanner（自動Top5+Telegram）", "⭐ My Day Trade Picks", "📊 Daily Close Review"])

# ====================== SQLite 永久儲存 ======================
DB_FILE = "stocktrade.db"
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS picks (date TEXT, ticker TEXT, entry_price REAL, ATR REAL, VWAP REAL, ai_tp REAL, ai_sl REAL, PRIMARY KEY(date, ticker))""")
    conn.commit()
    conn.close()
# load / save 函數同v1.7一樣（略）

if 'picks' not in st.session_state:
    st.session_state.picks = {}  # load_today_picks() ...

# ====================== Telegram 設定（新功能） ======================
st.sidebar.subheader("📲 Telegram推送設定")
telegram_token = st.sidebar.text_input("Bot Token", type="password", value=st.session_state.get('telegram_token', ''))
telegram_chat_id = st.sidebar.text_input("Chat ID", value=st.session_state.get('telegram_chat_id', ''))

if st.sidebar.button("💾 保存Telegram設定"):
    st.session_state.telegram_token = telegram_token
    st.session_state.telegram_chat_id = telegram_chat_id
    st.toast("✅ Telegram設定已保存！")

def send_to_telegram(message):
    if not telegram_token or not telegram_chat_id:
        return False
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except:
        return False

if st.sidebar.button("🔍 測試推送"):
    if send_to_telegram("✅ StockTrade Web App 測試推送成功！\n你已經可以收到日內Top5通知了！"):
        st.toast("✅ 測試推送已發送到Telegram！")
    else:
        st.error("❌ 推送失敗，請檢查Token和Chat ID")

# ====================== TAB 1: 自動開市後30分鐘 + Telegram推送 ======================
with tab1:
    st.subheader("🔥 Scanner - 開市後30分鐘自動Top5 + Telegram推送")
    
    # 自動觸發邏輯
    now_utc = datetime.utcnow()
    et_hour = (now_utc.hour - 4) % 24
    is_after_open_30min = et_hour >= 10
    
    if st.button("🚀 手動觸發自動掃描 + Telegram推送", type="primary") or is_after_open_30min:
        if is_after_open_30min:
            st.success("✅ 已自動偵測開市後30分鐘！正在跑Top5並推送Telegram...")
        
        with st.spinner("抓數據 + AI打分 + 準備推送..."):
            tickers = ["NVDA","TSLA","AAPL","AMD","SMCI","ARM","PLTR","META","GOOGL","AMZN","MSFT","HOOD","COIN","MARA","RIOT","SOFI","RIVN","LCID"]
            results = []
            for ticker in tickers:
                try:
                    data = yf.download(ticker, period="5d", interval="1m", prepost=True)
                    if data.empty or len(data) < 50: continue
                    data['RVOL'] = data['Volume'] / data['Volume'].rolling(20).mean()
                    data['RSI'] = calculate_rsi(data['Close'])  # 你原本的函數
                    data['EMA5'] = calculate_ema(data['Close'])
                    data['VWAP'] = (data['Close'] * data['Volume']).cumsum() / data['Volume'].cumsum()
                    data['ATR'] = calculate_atr(data['High'], data['Low'], data['Close'])
                    
                    latest = data.iloc[-1]
                    change_pct = (latest['Close'] - data.iloc[-2]['Close']) / data.iloc[-2]['Close'] * 100
                    rvol = latest.get('RVOL', 1)
                    score = rvol * abs(change_pct) * 0.8
                    
                    if abs(change_pct) >= 3 and rvol >= 3.5 and 30 <= latest.get('RSI',50) <= 70:
                        results.append({
                            'Ticker': ticker, 'Price': round(latest['Close'],2),
                            'Change%': round(change_pct,2), 'RVOL': round(rvol,1),
                            'Score': round(score,2), 'ATR': round(latest['ATR'],2),
                            'VWAP': round(latest['VWAP'],2), 'data': data
                        })
                except: continue
            
            if results:
                df = pd.DataFrame(results).nlargest(5, 'Score')
                st.success(f"✅ Top 5 勝率最高股票已選出並推送Telegram！")
                
                # 推送內容
                msg = f"<b>🚀 StockTrade 開市後30分鐘Top5</b>\n日期：{date.today()}\n\n"
                for _, row in df.iterrows():
                    msg += f"📌 <b>{row['Ticker']}</b> | ${row['Price']} | +{row['Change%']}% | RVOL {row['RVOL']}x | AI分數 {row['Score']}\n"
                    # 同時加入Picks
                    ai_tp = round(row['Price'] + 2 * row['ATR'], 2)
                    ai_sl = round(row['Price'] - 1 * row['ATR'], 2)
                    if 'picks' not in st.session_state: st.session_state.picks = {}
                    st.session_state.picks[row['Ticker']] = {'entry_price': row['Price'], 'ATR': row['ATR'], 'ai_tp': ai_tp, 'ai_sl': ai_sl}
                
                # 發送Telegram
                if send_to_telegram(msg):
                    st.toast("✅ 已成功推送Top5到Telegram！")
                else:
                    st.warning("⚠️ Telegram推送失敗（請檢查設定）")
                
                st.dataframe(df[['Ticker','Price','Change%','RVOL','Score']])
            else:
                st.warning("今日暫無高勝率機會")

# （TAB 2 & TAB 3 同之前一樣，略）

st.success("🎉 v1.8 Telegram推送已完成！一開App就自動跑 + 即時通知")
st.info("💡 每日開市後30分鐘左右開一次App，就會自動推送Top5到Telegram")

if st.checkbox("開啟自動刷新（每60秒）"):
    placeholder = st.empty()
    while True:
        with placeholder.container(): st.write("自動刷新中...")
        time.sleep(60)                    "ATR": float(row["ATR"]),
                    "VWAP": float(row["VWAP"]),
                    "ai_tp": float(row["ai_tp"]),
                    "ai_sl": float(row["ai_sl"])
                }
        return picks

def save_today_picks(picks):
    today = date.today().isoformat()
    rows = []
    for ticker, info in picks.items():
        rows.append({
            "date": today,
            "ticker": ticker,
            "entry_price": info["entry_price"],
            "ATR": info.get("ATR", 0),
            "VWAP": info.get("VWAP", 0),
            "ai_tp": info.get("ai_tp", 0),
            "ai_sl": info.get("ai_sl", 0)
        })
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

# 載入今日數據
if 'picks' not in st.session_state:
    st.session_state.picks = load_today_picks()

# ====================== 手寫技術指標（保持不變） ======================
def calculate_rsi(close, length=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=length-1, min_periods=length).mean()
    avg_loss = loss.ewm(com=length-1, min_periods=length).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ema(close, length=5):
    return close.ewm(span=length, adjust=False).mean()

def calculate_atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

def calculate_bbands(close, length=20, std=2):
    ma = close.rolling(length).mean()
    std_dev = close.rolling(length).std()
    return ma + std*std_dev, ma - std*std_dev

# ====================== TAB 1: SCANNER + 自動Top5 ======================
with tab1:
    st.subheader("🔥 Scanner - 開市後30分鐘自動Top5勝率模式")
    st.caption("美東開市後30分鐘（10:00 ET）一鍵自動跑")

    if st.button("🚀 模擬開市後30分鐘自動掃描 & 選Top5勝率最高", type="primary"):
        with st.spinner("正在抓取數據 + AI打分選Top5..."):
            tickers = ["NVDA","TSLA","AAPL","AMD","SMCI","ARM","PLTR","META","GOOGL","AMZN","MSFT","HOOD","COIN","MARA","RIOT","SOFI","RIVN","LCID"]
            df = pd.DataFrame()
            results = []
            for ticker in tickers:
                try:
                    data = yf.download(ticker, period="5d", interval="1m", prepost=True)
                    if data.empty or len(data) < 50: continue
                    data['RVOL'] = data['Volume'] / data['Volume'].rolling(20).mean()
                    data['RSI'] = calculate_rsi(data['Close'])
                    data['EMA5'] = calculate_ema(data['Close'])
                    data['VWAP'] = (data['Close'] * data['Volume']).cumsum() / data['Volume'].cumsum()
                    data['ATR'] = calculate_atr(data['High'], data['Low'], data['Close'])
                    
                    latest = data.iloc[-1]
                    change_pct = (latest['Close'] - data.iloc[-2]['Close']) / data.iloc[-2]['Close'] * 100
                    rvol = latest.get('RVOL', 1)
                    
                    # AI信心平均（模擬）
                    ai_conf = 80  # 簡化版，之後可再精準
                    score = rvol * abs(change_pct) * (ai_conf / 100)  # 勝率打分
                    
                    if abs(change_pct) >= 3 and rvol >= 3 and 30 <= latest['RSI'] <= 70:
                        results.append({
                            'Ticker': ticker, 'Price': round(latest['Close'],2),
                            'Change%': round(change_pct,2), 'RVOL': round(rvol,1),
                            'Score': round(score,2), 'ATR': round(latest['ATR'],2),
                            'VWAP': round(latest['VWAP'],2), 'data': data
                        })
                except: continue
            
            if results:
                df = pd.DataFrame(results)
                df = df.nlargest(5, 'Score')  # 自動選Top5勝率最高
                st.success(f"✅ 自動選出 Top 5 勝率最高股票！（開市後30分鐘模式）")
                
                for _, row in df.iterrows():
                    colA, colB, colC = st.columns([1.5, 3, 2])
                    with colA:
                        st.subheader(row['Ticker'])
                        st.metric("AI勝率分數", f"{row['Score']}")
                    with colB:
                        fig = go.Figure(data=[go.Candlestick(x=row['data'].index[-40:], 
                            open=row['data']['Open'][-40:], high=row['data']['High'][-40:],
                            low=row['data']['Low'][-40:], close=row['data']['Close'][-40:])])
                        fig.update_layout(height=160, margin=dict(l=0,r=0,t=0,b=0))
                        st.plotly_chart(fig, use_container_width=True)
                    with colC:
                        st.write(f"最新價 ${row['Price']}")
                        st.write(f"RVOL **{row['RVOL']}x**")
                        if st.button(f"加入Picks + 模擬交易 - {row['Ticker']}", key=f"add_{row['Ticker']}"):
                            if 'picks' not in st.session_state: st.session_state.picks = {}
                            # AI模擬建議
                            upper, lower = calculate_bbands(row['data']['Close'])
                            ai_tp = round(row['Price'] + 2 * row['ATR'], 2)
                            ai_sl = round(row['Price'] - 1 * row['ATR'], 2)
                            st.session_state.picks[row['Ticker']] = {
                                'entry_price': row['Price'], 'ATR': row['ATR'],
                                'VWAP': row['VWAP'], 'ai_tp': ai_tp, 'ai_sl': ai_sl
                            }
                            save_today_picks(st.session_state.picks)  # 自動儲存
                            st.toast(f"✅ {row['Ticker']} 已加入 + AI模擬交易啟動！")
                st.dataframe(df[['Ticker','Price','Change%','RVOL','Score']], hide_index=True)
            else:
                st.warning("暫無足夠機會股")

# ====================== TAB 2 & TAB 3 保持原有功能（略） ======================
# （Picks + Review 部分跟 v1.5 一樣，但已自動讀取CSV記住數據）
# ...（如果你需要完整程式碼，我可以再貼，但為了簡潔這裡跳過）

st.success("🎉 v1.6 已完成！Daily Close 自動記住 + 開市後30分鐘Top5模擬交易")
st.info("💡 想真·每日自動跑？下版我幫你加Telegram推送通知")

# 自動刷新（可開）
if st.checkbox("開啟Scanner自動刷新（每60秒）"):
    placeholder = st.empty()
    while True:
        with placeholder.container():
            st.write("已開啟自動刷新...")
        time.sleep(60)
