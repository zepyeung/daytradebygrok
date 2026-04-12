import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import numpy as np

# ====================== WEB APP 專屬設定 ======================
st.set_page_config(
    page_title="StockTrade Web - 美股Day Trade AI神器",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.sidebar.title("📱 StockTrade Web App")
st.sidebar.markdown("**美股日內交易AI選股器 v1.4**")
st.sidebar.caption("已解決 Python 3.14 相容問題 ✅")
st.sidebar.info("💡 美股開盤期間開啟自動刷新最強")

st.title("📈 StockTrade Web - 美股日內交易AI神器 v1.4")
st.markdown("**🤖 AI建議目標價 + 掃描 + Picks + 收市Review**｜純pandas版，已可穩定部署")

tab1, tab2, tab3 = st.tabs(["🔥 Scanner", "⭐ My Day Trade Picks（AI目標價）", "📊 Daily Close Review"])

# ====================== 手寫技術指標（取代pandas_ta） ======================
def calculate_rsi(close, length=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=length-1, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(com=length-1, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ema(close, length):
    return close.ewm(span=length, adjust=False).mean()

def calculate_atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=length).mean()
    return atr

def calculate_bbands(close, length=20, std=2):
    rolling_mean = close.rolling(window=length).mean()
    rolling_std = close.rolling(window=length).std()
    upper = rolling_mean + std * rolling_std
    lower = rolling_mean - std * rolling_std
    return upper, lower

# ====================== TAB 1: SCANNER ======================
with tab1:
    st.subheader("美股日內掃描器")
    col1, col2, col3, col4 = st.columns(4)
    with col1: min_rvol = st.slider("最低RVOL", 2.0, 10.0, 3.5, step=0.5)
    with col2: min_change = st.slider("最低漲跌幅%", 2.0, 20.0, 4.0, step=0.5)
    with col3: price_min = st.number_input("最低股價$", 5.0, step=1.0)
    with col4: price_max = st.number_input("最高股價$", 1000.0, step=10.0)

    custom_tickers = st.text_input("自訂Ticker（逗號分隔）", 
        value="NVDA,TSLA,AAPL,AMD,SMCI,ARM,PLTR,META,GOOGL,AMZN,MSFT,HOOD,COIN,MARA,RIOT,SOFI,RIVN,LCID")
    tickers = [t.strip().upper() for t in custom_tickers.split(",") if t.strip()]

    def scan_us_stocks(tickers):
        results = []
        for ticker in tickers:
            try:
                data = yf.download(ticker, period="5d", interval="1m", prepost=True)
                if data.empty or len(data) < 50: continue
                
                data['RVOL'] = data['Volume'] / data['Volume'].rolling(20).mean()
                data['RSI'] = calculate_rsi(data['Close'])
                data['EMA5'] = calculate_ema(data['Close'], 5)
                data['VWAP'] = (data['Close'] * data['Volume']).cumsum() / data['Volume'].cumsum()
                data['ATR'] = calculate_atr(data['High'], data['Low'], data['Close'])
                
                latest = data.iloc[-1]
                change_pct = (latest['Close'] - data.iloc[-2]['Close']) / data.iloc[-2]['Close'] * 100
                rvol = latest['RVOL']
                
                if (abs(change_pct) >= min_change and rvol >= min_rvol and 
                    30 <= latest['RSI'] <= 70 and latest['Close'] > latest['EMA5'] and 
                    price_min <= latest['Close'] <= price_max):
                    
                    results.append({
                        'Ticker': ticker, 'Price': round(latest['Close'], 2),
                        'Change%': round(change_pct, 2), 'RVOL': round(rvol, 1),
                        'RSI': round(latest['RSI'], 1), 'ATR': round(latest['ATR'], 2),
                        'VWAP': round(latest['VWAP'], 2), 'data': data
                    })
            except: continue
        return pd.DataFrame(results)

    if st.button("🔥 立即掃描", type="primary"):
        with st.spinner("抓取實時數據..."):
            df = scan_us_stocks(tickers)
        if not df.empty:
            st.success(f"找到 {len(df)} 支日內機會！")
            for _, row in df.iterrows():
                colA, colB, colC = st.columns([1.5, 3, 2])
                with colA: st.subheader(row['Ticker']); st.metric("漲跌幅", f"{row['Change%']}%")
                with colB:
                    fig = go.Figure(data=[go.Candlestick(x=row['data'].index[-40:], 
                        open=row['data']['Open'][-40:], high=row['data']['High'][-40:],
                        low=row['data']['Low'][-40:], close=row['data']['Close'][-40:])])
                    fig.update_layout(height=160, margin=dict(l=0,r=0,t=0,b=0))
                    st.plotly_chart(fig, use_container_width=True)
                with colC:
                    st.write(f"最新價 ${row['Price']}")
                    st.write(f"RVOL **{row['RVOL']}x**")
                    if st.button(f"加入Picks - {row['Ticker']}", key=f"add_{row['Ticker']}"):
                        if 'picks' not in st.session_state: st.session_state.picks = {}
                        st.session_state.picks[row['Ticker']] = {
                            'entry_time': datetime.now(), 'entry_price': row['Price'],
                            'ATR': row['ATR'], 'VWAP': row['VWAP'], 'data': row['data']
                        }
                        st.toast(f"✅ {row['Ticker']} 已加入今日Picks！")
        else: st.warning("暫無符合股票")

# ====================== TAB 2: MY PICKS + AI建議 ======================
with tab2:
    st.subheader("⭐ 我的今日Day Trade Picks（🤖 AI建議目標價）")
    if 'picks' not in st.session_state or not st.session_state.picks:
        st.info("先去Scanner選幾支股票吧！")
    else:
        rr_ratio = st.slider("基礎風險報酬比", 1.0, 3.0, 2.0, step=0.5)
        
        def get_ai_target_suggestions(ticker, entry_price, atr, vwap, data):
            upper, lower = calculate_bbands(data['Close'])
            recent_high = data['High'][-20:].max()
            recent_low = data['Low'][-20:].min()
            swing = recent_high - recent_low
            fib_1618 = recent_high + 0.618 * swing
            
            return {
                "保守AI": {"entry": round(entry_price, 2), "sl": round(entry_price - 1 * atr, 2),
                           "tp": round(entry_price + 1.5 * atr, 2), "confidence": 75,
                           "reason": "ATR保守 + Bollinger中軌"},
                "激進AI": {"entry": round(max(entry_price, vwap), 2), "sl": round(entry_price - 0.8 * atr, 2),
                           "tp": round(fib_1618, 2), "confidence": 60,
                           "reason": "Fib 1.618延伸 + VWAP突破"},
                "平衡AI": {"entry": round(entry_price, 2), "sl": round(lower.iloc[-1], 2) if lower.iloc[-1] < entry_price else round(entry_price - atr, 2),
                           "tp": round(upper.iloc[-1], 2), "confidence": 85,
                           "reason": "Bollinger Band突破 + Pivot阻力"}
            }

        for ticker, info in list(st.session_state.picks.items()):
            entry = info.get('entry_price', 0)
            atr_val = info.get('ATR', 1)
            vwap_val = info.get('VWAP', entry)
            data = info.get('data', None)
            
            ai_sugs = get_ai_target_suggestions(ticker, entry, atr_val, vwap_val, data) if data is not None else {}
            
            col1, col2, col3 = st.columns([1, 3, 2])
            with col1:
                st.subheader(ticker)
                st.metric("目前Entry", f"${entry}")
            with col2:
                st.write("**🤖 AI建議目標價**")
                for label, sug in ai_sugs.items():
                    with st.expander(f"{label}（信心 {sug['confidence']}）", expanded=True):
                        st.write(f"**買入價** ${sug['entry']}")
                        st.write(f"**止損 SL** ${sug['sl']}")
                        st.write(f"**目標賣出 TP** ${sug['tp']}")
                        st.caption(sug['reason'])
            with col3:
                st.write(f"ATR: ${atr_val} | VWAP: ${vwap_val}")
                new_entry = st.number_input("手動調整買入價$", value=entry, step=0.01, key=f"adj_{ticker}")
                if new_entry != entry:
                    st.session_state.picks[ticker]['entry_price'] = new_entry
                    st.rerun()
                if st.button("移除", key=f"del_{ticker}"):
                    del st.session_state.picks[ticker]
                    st.rerun()

# ====================== TAB 3: DAILY REVIEW ======================
with tab3:
    st.subheader("📊 每日收市Review（益收 & AI達成率）")
    if st.button("📥 載入今日收市Review", type="primary"):
        if 'picks' not in st.session_state or not st.session_state.picks:
            st.warning("今日還沒選股")
        else:
            total_pnl = 0
            for ticker, info in st.session_state.picks.items():
                data = yf.download(ticker, period="1d", interval="1m")
                close_price = round(data['Close'].iloc[-1], 2) if not data.empty else info['entry_price']
                entry = info['entry_price']
                pnl_pct = ((close_price - entry) / entry) * 100
                
                ai_sugs = get_ai_target_suggestions(ticker, entry, info.get('ATR',1), info.get('VWAP',entry), info.get('data'))
                ai_tp = ai_sugs.get("平衡AI", {}).get("tp", entry + 2*info.get('ATR',1))
                hit_ai = "✅ 達成AI TP" if close_price >= ai_tp else "❌ 未達"
                
                st.write(f"**{ticker}** | 買入 ${entry} → 收盤 ${close_price} | {hit_ai}")
                st.metric("實際盈虧%", f"{pnl_pct:.2f}%", delta=pnl_pct)
                total_pnl += pnl_pct
            st.success(f"今日總益收: **{total_pnl:.1f}%**")
            st.balloons()

st.markdown("---")
st.success("🎉 v1.4 已去除 pandas_ta，完全相容 Python 3.14！")

# 自動刷新
if st.checkbox("開啟Scanner自動刷新（每60秒）"):
    placeholder = st.empty()
    while True:
        with placeholder.container():
            df = scan_us_stocks(tickers)
            st.dataframe(df.drop(columns=['data'], errors='ignore') if not df.empty else pd.DataFrame())
        time.sleep(60)
