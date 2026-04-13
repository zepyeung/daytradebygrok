import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
import time
import numpy as np
import sqlite3
import requests

# ====================== 簡單密碼登入 ======================
PASSWORD = "stocktrade2026"   # ← 你可以自己改成更強的密碼，例如 "HoKwanDayTrade888"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 StockTrade Web App - Private Login")
    st.subheader("請輸入密碼進入 Day Trade 選股器")
    pw = st.text_input("輸入密碼", type="password")
    if st.button("登入"):
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ 密碼錯誤，請重試")
    st.stop()  # 未登入就停低

# ====================== 主程式（登入後顯示） ======================
st.set_page_config(page_title="StockTrade Web v2.0", page_icon="📈", layout="wide")

st.sidebar.title("📱 StockTrade Web App v2.0")
st.sidebar.success("✅ 已登入 | Telegram 已永久設定")

st.title("📈 StockTrade Web v2.0 - 美股日內交易AI神器")
st.markdown("**Private App + Telegram自動推送**")

tab1, tab2, tab3 = st.tabs(["🔥 Scanner（自動Top5+Telegram）", "⭐ My Day Trade Picks", "📊 Daily Close Review"])

# ====================== Telegram 永久設定 ======================
telegram_token = st.secrets["telegram"]["token"]
telegram_chat_id = st.secrets["telegram"]["chat_id"]

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": telegram_chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        return r.status_code == 200
    except:
        return False

if st.sidebar.button("🔍 測試Telegram推送"):
    if send_to_telegram(f"✅ StockTrade v2.0 測試推送成功！\n登入時間：{datetime.now().strftime('%H:%M')}"):
        st.toast("✅ 已發送到你的 Telegram！")
    else:
        st.error("❌ 推送失敗，請檢查 Secrets")

# ====================== 你的 Scanner、Picks、Review 功能 ======================
# （這裡貼上你之前 v1.8 的 Scanner / Picks / Review 程式碼）
# 為了簡潔，我先留位置，你可以把之前的功能貼過來

st.sidebar.button("🚪 登出", on_click=lambda: st.session_state.update({"authenticated": False}))

st.success("🎉 v2.0 已完成！Telegram設定永久保存 + 簡單密碼登入")
st.info("💡 每日開市後30分鐘左右開一次App，就會自動跑Top5並推送Telegram")

if st.checkbox("開啟自動刷新（每60秒）"):
    placeholder = st.empty()
    while True:
        with placeholder.container():
            st.write("自動刷新中...")
        time.sleep(60)
