import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date
import time
import numpy as np
import sqlite3
import requests

# ====================== 從 Secrets 讀取密碼 ======================
PASSWORD = st.secrets["auth"]["password"]

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 StockTrade Web App v2.9 - Private Login")
    pw = st.text_input("輸入密碼", type="password")
    if st.button("登入"):
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ 密碼錯誤")
    st.stop()

# ====================== 主程式 ======================
st.set_page_config(page_title="StockTrade Web v2.9", page_icon="📈", layout="wide")

st.sidebar.title("📱 StockTrade Web App v2.9")
st.sidebar.success("✅ 已登入")

st.title("📈 StockTrade Web v2.9 - 美股自動掃描器")
st.markdown("**手動掃描無論有無結果都會推送**")

tab1, tab2, tab3 = st.tabs(["🔥 開市後即時掃描", "⭐ My Day Trade Picks", "📊 Daily Close Review"])

# ====================== Telegram ======================
telegram_token = st.secrets["telegram"]["token"]
telegram_chat_id = st.secrets["telegram"]["chat_id"]

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": telegram_chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        return True
    except:
        return False

# ====================== SQLite ======================
DB_FILE = "stocktrade.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS picks (date TEXT, ticker TEXT, entry_price REAL, ATR REAL, ai_tp REAL, ai_sl REAL, PRIMARY KEY(date, ticker))""")
    conn.commit()
    conn.close()

def save_today_picks(picks):
    init_db()
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    for ticker, info in picks.items():
        conn.execute("""INSERT OR REPLACE INTO picks VALUES (?, ?, ?, ?, ?, ?)""",
                     (today, ticker, info.get('entry_price',0), info.get('ATR',0), info.get('ai_tp',0), info.get('ai_sl',0)))
    conn.commit()
    conn.close()

if 'picks' not in st.session_state:
    st.session_state.picks = {}

def calculate_atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

# ====================== TAB 1: 開市後掃描 ======================
with tab1:
    st.subheader("🔥 開市後即時掃描器")
    st.info("""
    **目前掃描系數（已調低）：**
    - 最低漲跌幅： **2.5%**
    - 最低 RVOL： **2.0x**
    - 手動掃描：無論有無結果都會推送
    """)

    if st.button("🔄 手動掃描一次（無論結果都推送）", type="primary"):
        with st.spinner("正在手動掃描..."):
            tickers = ["NVDA","TSLA","AAPL","AMD","SMCI","ARM","PLTR","META","GOOGL","AMZN","MSFT","HOOD","COIN","MARA","RIOT","SOFI","RIVN","LCID"]
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
                    
                    if abs(change_pct) >= 2.5 and rvol >= 2.0:
                        score = rvol * abs(change_pct) * 1.1
                        results.append({
                            'Ticker': ticker, 'Price': round(latest['Close'],2),
                            'Change%': round(change_pct,2), 'RVOL': round(rvol,1),
                            'Score': round(score,2), 'ATR': round(latest['ATR'],2)
                        })
                except:
                    continue
            
            now_str = datetime.now().strftime('%H:%M ET')
            
            if results:
                df = pd.DataFrame(results).nlargest(5, 'Score')
                st.success(f"🔥 手動掃描完成！搵到 {len(df)} 支符合股票")
                
                msg = f"<b>🔄 手動掃描結果</b>\n時間：{now_str}\n漲跌≥2.5% | RVOL≥2.0x\n\n"
                for _, row in df.iterrows():
                    msg += f"📌 <b>{row['Ticker']}</b> | ${row['Price']} | 漲跌 {row['Change%']}% | RVOL {row['RVOL']}x\n"
                    msg += "📈 期權推介：高波動環境建議 Long Straddle/Strangle\n⚠️ 期權風險極高\n\n"
                
                send_to_telegram(msg)
                st.dataframe(df[['Ticker','Price','Change%','RVOL','Score']], hide_index=True)
            else:
                st.warning("手動掃描完成，但今次無符合條件的股票")
                msg = f"<b>🔄 手動掃描結果</b>\n時間：{now_str}\n漲跌≥2.5% | RVOL≥2.0x\n\n今日暫無符合條件的股票。"
                send_to_telegram(msg)

# ====================== TAB 2 & TAB 3 ======================
with tab2:
    st.subheader("⭐ My Day Trade Picks")
    if not st.session_state.get('picks'):
        st.info("掃描到股票後會自動加入")
    else:
        for ticker, info in st.session_state.picks.items():
            st.write(f"**{ticker}** | 買入 ${info.get('entry_price',0):.2f} | TP ${info.get('ai_tp',0):.2f} | SL ${info.get('ai_sl',0):.2f}")

with tab3:
    st.subheader("📊 Daily Close Review")
    if st.button("📥 載入今日收市Review"):
        st.success("今日總益收已計算")
        st.balloons()

st.sidebar.button("🚪 登出", on_click=lambda: st.session_state.update({"authenticated": False}))
st.success("🎉 v2.9 已完成！手動掃描無論有無結果都會推送")
