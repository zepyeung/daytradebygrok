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
PASSWORD = "stocktrade2026"   # ← 可自行修改

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 StockTrade Web App v2.4 - Private Login")
    pw = st.text_input("輸入密碼", type="password")
    if st.button("登入"):
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ 密碼錯誤")
    st.stop()

# ====================== 主程式 ======================
st.set_page_config(page_title="StockTrade Web v2.4", page_icon="📈", layout="wide")

st.sidebar.title("📱 StockTrade Web App v2.4")
st.sidebar.success("✅ 已登入")

st.title("📈 StockTrade Web v2.4 - 美股 Pre-Market AI神器")
st.markdown("**開市前30分鐘自動掃描 + 期權推介**")

tab1, tab2, tab3 = st.tabs(["🔥 Pre-Market Scanner", "⭐ My Day Trade Picks", "📊 Daily Close Review"])

# ====================== Telegram ======================
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
    if send_to_telegram("✅ StockTrade v2.4 測試推送成功！"):
        st.toast("✅ 已發送到Telegram！")
    else:
        st.error("❌ 推送失敗")

# ====================== SQLite 永久儲存 ======================
DB_FILE = "stocktrade.db"
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS picks (date TEXT, ticker TEXT, entry_price REAL, ATR REAL, VWAP REAL, ai_tp REAL, ai_sl REAL, PRIMARY KEY(date, ticker))""")
    conn.commit()
    conn.close()

def load_today_picks():
    init_db()
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql(f"SELECT * FROM picks WHERE date='{today}'", conn)
    conn.close()
    picks = {}
    for _, row in df.iterrows():
        picks[row['ticker']] = {'entry_price': row['entry_price'], 'ATR': row['ATR'], 'ai_tp': row['ai_tp'], 'ai_sl': row['ai_sl']}
    return picks

def save_today_picks(picks):
    init_db()
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    for ticker, info in picks.items():
        conn.execute("""INSERT OR REPLACE INTO picks VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (today, ticker, info.get('entry_price',0), info.get('ATR',0), 0, info.get('ai_tp',0), info.get('ai_sl',0)))
    conn.commit()
    conn.close()

if 'picks' not in st.session_state:
    st.session_state.picks = load_today_picks()

# ====================== 技術指標 ======================
def calculate_rsi(close, length=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=length-1, min_periods=length).mean()
    avg_loss = loss.ewm(com=length-1, min_periods=length).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

# ====================== TAB 1: Pre-Market Scanner ======================
with tab1:
    st.subheader("🔥 Pre-Market Scanner - 開市前30分鐘模式")

    # === 清楚顯示目前使用的系數 ===
    st.info(f"""
    **目前使用的掃描系數：**
    - 最低 Gap： **4.0%**
    - 最低 RVOL： **3.0x**
    - AI 分數計算： RVOL × |Gap%| × 1.1
    """)

    st.caption("美東時間 9:00 AM（開市前30分鐘）自動掃描")

    # 時間檢查
    now_utc = datetime.utcnow()
    et_hour = (now_utc.hour - 4) % 24
    is_pre_market = (et_hour == 9) or (et_hour == 8 and now_utc.minute >= 30)

    if st.button("🚀 觸發 Pre-Market 掃描 + Telegram推送", type="primary") or is_pre_market:
        if is_pre_market:
            st.success("✅ 已自動偵測開市前30分鐘！正在掃描...")

        with st.spinner("抓取數據 + 選Top5..."):
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
                    score = rvol * abs(change_pct) * 1.1
                    
                    if abs(change_pct) >= 4.0 and rvol >= 3.0:
                        results.append({
                            'Ticker': ticker, 'Price': round(latest['Close'],2),
                            'Gap%': round(change_pct,2), 'RVOL': round(rvol,1),
                            'Score': round(score,2), 'ATR': round(latest['ATR'],2)
                        })
                except: continue
            
            if results:
                df = pd.DataFrame(results).nlargest(5, 'Score')
                st.success(f"✅ Pre-Market Top 5 已選出！（Gap≥4% | RVOL≥3.0x）")
                
                msg = f"<b>🚀 StockTrade Pre-Market Top5</b>\n時間：{datetime.now().strftime('%H:%M ET')}\nGap≥4% | RVOL≥3.0x\n\n"
                for _, row in df.iterrows():
                    msg += f"📌 <b>{row['Ticker']}</b> | ${row['Price']} | Gap {row['Gap%']}% | RVOL {row['RVOL']}x\n"
                    
                    # 期權推介
                    option_note = "高IV環境，建議：\n• Long Straddle / Strangle（買大波動）\n• Credit Spread（如果預期收窄）\n⚠️ 期權風險極高"
                    msg += f"📈 期權推介：{option_note}\n\n"
                    
                    # 加入Picks
                    ai_tp = round(row['Price'] + 2 * row['ATR'], 2)
                    ai_sl = round(row['Price'] - 1 * row['ATR'], 2)
                    if 'picks' not in st.session_state: st.session_state.picks = {}
                    st.session_state.picks[row['Ticker']] = {'entry_price': row['Price'], 'ATR': row['ATR'], 'ai_tp': ai_tp, 'ai_sl': ai_sl}
                    save_today_picks(st.session_state.picks)
                
                if send_to_telegram(msg):
                    st.toast("✅ 已推送Top5 + 期權推介到Telegram！")
                else:
                    st.warning("Telegram推送失敗")
                
                st.dataframe(df[['Ticker','Price','Gap%','RVOL','Score']], hide_index=True)
            else:
                st.warning("今日Pre-Market暫無符合條件的股票")

# ====================== TAB 2 & TAB 3（簡化版） ======================
with tab2:
    st.subheader("⭐ My Day Trade Picks")
    if not st.session_state.get('picks'):
        st.info("掃描後會自動加入")
    else:
        for ticker, info in st.session_state.picks.items():
            st.write(f"**{ticker}** | 買入 ${info.get('entry_price',0):.2f} | TP ${info.get('ai_tp',0):.2f} | SL ${info.get('ai_sl',0):.2f}")

with tab3:
    st.subheader("📊 Daily Close Review")
    if st.button("📥 載入今日收市Review", type="primary"):
        st.success("今日總益收計算完成（模擬）")
        st.balloons()

st.sidebar.button("🚪 登出", on_click=lambda: st.session_state.update({"authenticated": False}))

st.info("""
**重要提示：**
- 目前必須開啟App才會觸發掃描 + 推送
- 如果想「完全唔開App都有推送」，我可以幫你加 GitHub Actions 每日自動推送
""")

st.success("🎉 v2.4 已完成！目前系數已清楚顯示")
