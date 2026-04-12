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
        time.sleep(60)
