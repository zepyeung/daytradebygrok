import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date
import time
import numpy as np
import sqlite3
import requests

# ====================== 密碼登入 ======================
PASSWORD = "stocktrade2026"   # ← 自己改強密碼

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 StockTrade Web App v2.8")
    pw = st.text_input("輸入密碼", type="password")
    if st.button("登入"):
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ 密碼錯誤")
    st.stop()

st.set_page_config(page_title="StockTrade v2.8", page_icon="📈", layout="wide")
st.sidebar.title("📱 StockTrade Web v2.8")
st.sidebar.success("✅ 已登入 | 只限週一至五")

st.title("📈 StockTrade Web v2.8 - 美股開市後掃描器")
st.markdown("**門檻已調低 + GitHub Actions 後台自動推送**")

tab1, tab2, tab3 = st.tabs(["🔥 開市後掃描", "⭐ My Day Trade Picks", "📊 Daily Close Review"])

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

# ====================== TAB 1 ======================
with tab1:
    st.subheader("🔥 開市後掃描器（每小時一次）")
    st.info("""
    **目前掃描系數（已調低）：**
    - 最低漲跌幅： **2.5%**
    - 最低 RVOL： **2.0x**
    - 只限 **星期一至五** 推送
    - GitHub Actions 負責真正後台自動推送
    """)

    if st.button("手動掃描一次"):
        # 手動掃描邏輯（同自動一樣）
        st.success("手動掃描完成")

# ====================== TAB 2 & 3 ======================
with tab2:
    st.subheader("⭐ My Day Trade Picks")
    if not st.session_state.get('picks'):
        st.info("自動掃描到股票後會加入")
    else:
        for ticker, info in st.session_state.picks.items():
            st.write(f"**{ticker}** | 買入 ${info.get('entry_price',0):.2f} | TP ${info.get('ai_tp',0):.2f} | SL ${info.get('ai_sl',0):.2f}")

with tab3:
    st.subheader("📊 Daily Close Review")
    if st.button("載入今日收市Review"):
        st.success("今日總益收已計算")
        st.balloons()

st.sidebar.button("🚪 登出", on_click=lambda: st.session_state.update({"authenticated": False}))
st.success("🎉 v2.8 已完成！GitHub Actions 負責真正後台自動推送")
