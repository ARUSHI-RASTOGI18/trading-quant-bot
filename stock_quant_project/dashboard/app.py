"""
Stock Quant Analysis Dashboard
dashboard/app.py — UI layer only.
Backend modules are imported unchanged.
"""

import os
import sys
import time
from datetime import datetime

import requests
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_root = os.path.join(os.path.dirname(__file__), "..")
for _p in ("data", "indicators", "strategies", "backtesting", "dashboard"):
    sys.path.append(os.path.join(_root, _p))

from data_fetcher       import fetch_stock_data
from indicators         import calculate_indicators
from trading_strategies import run_strategies, strategies_info
from backtester         import backtest
from chart_generator    import generate_chart

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Stock Quant Analysis Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Auto-refresh every 30 s
# ---------------------------------------------------------------------------
refresh_count = st_autorefresh(interval=30_000, key="autorefresh")

# ---------------------------------------------------------------------------
# Session-state defaults
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "analysis_run":          False,
    "last_symbol":           "AAPL",
    "last_timeframe":        "1d",
    "last_signals":          ["MA_signal", "MACD_signal_trade", "EMA_signal"],
    "last_show_sma":         True,
    "last_show_ema":         True,
    "last_show_bb":          True,
    "last_updated":          None,
    "active_chart_strategy": None,
    "market":                "US Market",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PERIOD_MAP = {"15m": "5d", "30m": "1mo", "1h": "3mo", "1d": "6mo"}

STRATEGY_LABELS = {
    "MA_signal":         "Moving Average",
    "RSI_signal":        "RSI",
    "MACD_signal_trade": "MACD",
    "BB_signal":         "Bollinger Bands",
    "EMA_signal":        "EMA Crossover",
}

SIGNAL_KEY_MAP = {
    "MA_signal":         "ma",
    "RSI_signal":        "rsi",
    "MACD_signal_trade": "macd",
    "BB_signal":         "bb",
    "EMA_signal":        "ema",
}

# Fallback tickers shown before the user types anything (US Market)
FALLBACK_TICKERS = [
    "AAPL", "TSLA", "NVDA", "MSFT", "GOOGL",
    "AMZN", "META", "NFLX", "AMD",  "INTC",
]

# NIFTY 50 constituent tickers (Indian Market)
NIFTY50_TICKERS = [
    "RELIANCE.NS",  "TCS.NS",       "HDFCBANK.NS",  "INFY.NS",
    "ICICIBANK.NS", "HINDUNILVR.NS","ITC.NS",        "SBIN.NS",
    "BHARTIARTL.NS","KOTAKBANK.NS", "LT.NS",         "ASIANPAINT.NS",
    "AXISBANK.NS",  "MARUTI.NS",    "TITAN.NS",      "BAJFINANCE.NS",
    "ULTRACEMCO.NS","NTPC.NS",      "NESTLEIND.NS",  "POWERGRID.NS",
    "TATASTEEL.NS", "HCLTECH.NS",   "WIPRO.NS",      "SUNPHARMA.NS",
    "TECHM.NS",     "ADANIENT.NS",  "ADANIPORTS.NS", "JSWSTEEL.NS",
    "ONGC.NS",      "COALINDIA.NS", "DRREDDY.NS",    "EICHERMOT.NS",
    "GRASIM.NS",    "HINDALCO.NS",  "INDUSINDBK.NS", "BAJAJFINSV.NS",
    "BRITANNIA.NS", "CIPLA.NS",     "DIVISLAB.NS",   "HEROMOTOCO.NS",
    "M&M.NS",       "SHREECEM.NS",  "TATACONSUM.NS", "UPL.NS",
    "VEDL.NS",      "BPCL.NS",      "APOLLOHOSP.NS", "DABUR.NS",
    "PIDILITIND.NS",
]

# ---------------------------------------------------------------------------
# Dynamic Yahoo Finance ticker search
# ---------------------------------------------------------------------------
_YF_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
_YF_HEADERS    = {"User-Agent": "Mozilla/5.0"}


@st.cache_data(ttl=60, show_spinner=False)
def fetch_ticker_suggestions(query: str, market: str = "US Market") -> list[str]:
    """
    Return ticker suggestions based on the selected market.

    Indian Market (NIFTY 50):
        Filters NIFTY50_TICKERS client-side — no network call needed.
        Empty query returns the full list; otherwise filters by substring match.

    US Market:
        Queries the Yahoo Finance search API and returns up to 10 results.
        Results are cached for 60 seconds to avoid flooding the API.
        Falls back to FALLBACK_TICKERS on any network or parse error.

    Args:
        query:  Partial ticker or company name typed by the user.
        market: "US Market" or "Indian Market (NIFTY 50)".

    Returns:
        List of ticker symbol strings.
    """
    query = query.strip()

    # ── Indian Market — pure client-side filter, no HTTP request ──────────
    if market == "Indian Market (NIFTY 50)":
        if not query:
            return NIFTY50_TICKERS
        return [t for t in NIFTY50_TICKERS if query.upper() in t] or NIFTY50_TICKERS

    # ── US Market — Yahoo Finance live search ─────────────────────────────
    if not query:
        return FALLBACK_TICKERS

    try:
        resp = requests.get(
            _YF_SEARCH_URL,
            params={"q": query, "lang": "en-US", "region": "US",
                    "quotesCount": 10, "newsCount": 0},
            headers=_YF_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        data    = resp.json()
        quotes  = data.get("quotes", [])
        symbols = [
            q["symbol"]
            for q in quotes
            if q.get("symbol")
            and q.get("quoteType", "") in ("EQUITY", "ETF", "MUTUALFUND", "")
            and "." not in q["symbol"]          # skip non-US exchanges (e.g. BP.L)
        ]
        return symbols[:10] if symbols else FALLBACK_TICKERS
    except Exception:
        return FALLBACK_TICKERS

INDICATOR_EXPLAINERS = {
    "MA_signal": {
        "name": "Moving Average  (SMA 20 vs EMA 20)",
        "body": (
            "The Moving Average strategy compares a 20-period Simple Moving Average "
            "(SMA) with a 20-period Exponential Moving Average (EMA). The SMA weights "
            "all periods equally and reacts slowly to price changes. The EMA gives more "
            "weight to recent prices and reacts faster. When the SMA rises above the EMA "
            "the market is trending upward; when it falls below, a downtrend is indicated."
        ),
        "rules": [
            ("SMA 20 > EMA 20", "BUY"),
            ("SMA 20 < EMA 20", "SELL"),
            ("SMA 20 = EMA 20", "HOLD"),
        ],
    },
    "RSI_signal": {
        "name": "RSI  —  Relative Strength Index (14)",
        "body": (
            "RSI measures the speed and magnitude of recent price changes on a scale "
            "of 0 to 100. A reading below 30 suggests the asset is oversold and may "
            "recover. A reading above 70 suggests the asset is overbought and may "
            "pull back. Between those thresholds the trend is considered neutral."
        ),
        "rules": [
            ("RSI 14 < 30  (oversold)",   "BUY"),
            ("RSI 14 > 70  (overbought)", "SELL"),
            ("30 to 70",                   "HOLD"),
        ],
    },
    "MACD_signal_trade": {
        "name": "MACD  —  Moving Average Convergence Divergence",
        "body": (
            "MACD is computed as EMA(12) minus EMA(26). A 9-period EMA of the MACD "
            "line, called the signal line, is plotted alongside it. When the MACD "
            "crosses above the signal line bullish momentum is building. When it "
            "crosses below, bearish momentum is taking over."
        ),
        "rules": [
            ("MACD crosses above signal line", "BUY"),
            ("MACD crosses below signal line", "SELL"),
            ("No crossover",                    "HOLD"),
        ],
    },
    "BB_signal": {
        "name": "Bollinger Bands  (20-period, 2 standard deviations)",
        "body": (
            "Bollinger Bands place an upper and lower bound at two standard deviations "
            "above and below a 20-period SMA. Wide bands indicate high volatility; "
            "narrow bands indicate low volatility. Price touching the lower band "
            "suggests the asset may be oversold; touching the upper band suggests "
            "it may be overbought."
        ),
        "rules": [
            ("Close < Lower Band", "BUY"),
            ("Close > Upper Band", "SELL"),
            ("Close between bands", "HOLD"),
        ],
    },
    "EMA_signal": {
        "name": "EMA Crossover  (EMA 12 vs EMA 26)",
        "body": (
            "The EMA Crossover strategy uses two exponential moving averages: "
            "EMA(12) as the fast line and EMA(26) as the slow line. When the fast "
            "line crosses above the slow line, short-term momentum is shifting "
            "upward. When it crosses below, momentum is shifting downward."
        ),
        "rules": [
            ("EMA 12 crosses above EMA 26", "BUY"),
            ("EMA 12 crosses below EMA 26", "SELL"),
            ("No crossover",                 "HOLD"),
        ],
    },
}

# ---------------------------------------------------------------------------
# CSS — clean, minimal dark theme, zero emojis
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

:root {
    --bg:        #0A0E14;
    --surface:   #0F1620;
    --surface-2: #141E2B;
    --border:    #1C2B3A;
    --border-2:  #243447;
    --accent:    #3B9EFF;
    --green:     #23D18B;
    --red:       #F14C60;
    --amber:     #E8A838;
    --text-hi:   #E8EDF2;
    --text-mid:  #8899AA;
    --text-lo:   #3D5166;
    --body:      'DM Sans', sans-serif;
    --mono:      'DM Mono', monospace;
    --r:         8px;
    --r-lg:      12px;
}

html, body, .stApp {
    background: var(--bg) !important;
    color: var(--text-hi);
    font-family: var(--body);
}
[data-testid="stSidebar"] { display: none !important; }
.block-container {
    padding: 2.5rem 3rem 5rem !important;
    max-width: 1320px !important;
    margin: 0 auto;
}
p, li { color: var(--text-mid); font-size: 14px; line-height: 1.75; }
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 2.5rem 0 !important; }

/* ── Page heading (centered) ── */
.page-header {
    text-align: center;
    padding: 36px 24px 28px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 28px;
}
.page-title {
    font-size: clamp(22px, 3.5vw, 32px);
    font-weight: 600;
    color: var(--text-hi);
    letter-spacing: -0.4px;
    margin-bottom: 8px;
}
.page-desc {
    font-size: 14px;
    color: var(--text-mid);
    max-width: 640px;
    margin: 0 auto 10px;
    line-height: 1.7;
}
.page-meta {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-lo);
    margin-top: 6px;
}
.live-badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-family: var(--mono); font-size: 11px; color: var(--green);
    background: rgba(35,209,139,.07); border: 1px solid rgba(35,209,139,.2);
    border-radius: 20px; padding: 3px 10px; margin-left: 10px;
    vertical-align: middle;
}
.live-dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: var(--green); animation: blink 2s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.2} }

/* ── Control panel ── */
.ctrl-wrap {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 20px 24px 16px;
    margin-bottom: 28px;
}

/* ── Section headings ── */
.sec-head {
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.9px;
    text-transform: uppercase;
    color: var(--text-lo);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin: 36px 0 18px;
}

/* ── KPI cards ── */
.kpi-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 18px 16px;
    text-align: center;
}
.kpi-label {
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.7px;
    text-transform: uppercase; color: var(--text-lo); margin-bottom: 10px;
}
.kpi-val {
    font-family: var(--mono); font-size: 22px; font-weight: 500;
    color: var(--text-hi);
}
.kpi-val.pos { color: var(--green); }
.kpi-val.neg { color: var(--red); }

/* ── Chip signals ── */
.chip {
    display: inline-block; font-family: var(--mono); font-size: 11px;
    border-radius: 4px; padding: 2px 8px; font-weight: 500;
}
.chip.buy  { background: rgba(35,209,139,.1);  color:var(--green); border:1px solid rgba(35,209,139,.25); }
.chip.sell { background: rgba(241,76,96,.1);   color:var(--red);   border:1px solid rgba(241,76,96,.25);  }
.chip.hold { background: rgba(232,168,56,.1);  color:var(--amber); border:1px solid rgba(232,168,56,.25); }

/* ── Explainer cards ── */
.explainer {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r); padding: 20px 22px; height: 100%;
}
.explainer-name {
    font-size: 13px; font-weight: 600; color: var(--text-hi); margin-bottom: 10px;
}
.explainer-body { font-size: 13px; color: var(--text-mid); line-height: 1.75; }
.rule-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 0; border-top: 1px solid var(--border);
    font-family: var(--mono); font-size: 11px;
}
.rule-cond { color: var(--text-mid); }

/* ── Signal panel (below chart) ── */
.signal-panel {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r); padding: 20px 22px;
    margin-top: 16px;
}
.signal-panel-title {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.8px;
    text-transform: uppercase; color: var(--text-lo); margin-bottom: 14px;
}
.signal-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 7px 0; border-bottom: 1px solid var(--border);
    font-size: 13px;
}
.signal-row:last-child { border-bottom: none; }
.signal-name { color: var(--text-mid); font-family: var(--mono); font-size: 12px; }

/* ── Strategy how-it-works card ── */
.how-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r); padding: 20px 22px; margin-top: 16px;
}
.how-card-title {
    font-size: 13px; font-weight: 600; color: var(--text-hi); margin-bottom: 10px;
}
.how-card-body { font-size: 13px; color: var(--text-mid); line-height: 1.75; }
.how-card-rules {
    font-family: var(--mono); font-size: 12px; color: var(--amber);
    margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border);
}

/* ── Strategy reference cards ── */
.strat-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r); padding: 20px 22px; margin-bottom: 14px;
}
.strat-name { font-size: 14px; font-weight: 600; color: var(--text-hi); margin-bottom: 6px; }
.strat-desc { font-size: 13px; color: var(--text-mid); line-height: 1.7; margin-bottom: 10px; }
.strat-rules { font-family: var(--mono); font-size: 11px; color: var(--amber); }

/* ── Empty state / feature cards ── */
.feat-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-lg); padding: 28px 24px;
}
.feat-title { font-size: 14px; font-weight: 600; color: var(--text-hi); margin-bottom: 8px; }
.feat-desc  { font-size: 13px; color: var(--text-mid); line-height: 1.65; }

/* ── Footer ── */
.footer {
    text-align: center; padding: 24px 0 8px;
    font-family: var(--mono); font-size: 11px; color: var(--text-lo);
    border-top: 1px solid var(--border); margin-top: 56px;
}

/* ── Strategy flashcards ── */
.flashcard-section {
    margin: 0 0 24px;
}
.flashcard-section-label {
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.9px;
    text-transform: uppercase;
    color: var(--text-lo);
    margin-bottom: 14px;
}
.flashcard {
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 2px solid var(--accent);
    border-radius: var(--r);
    padding: 16px 18px;
    height: 100%;
}
.fc-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-hi);
    margin-bottom: 6px;
}
.fc-desc {
    font-size: 12px;
    color: var(--text-mid);
    line-height: 1.6;
    margin-bottom: 10px;
}
.fc-rules {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-lo);
    border-top: 1px solid var(--border);
    padding-top: 8px;
    line-height: 1.8;
}

/* ── Streamlit widget overrides ── */
div.stButton > button {
    background: var(--surface-2); color: var(--text-hi);
    border: 1px solid var(--border-2); border-radius: var(--r);
    font-family: var(--body); font-size: 13px; font-weight: 500;
    padding: 9px 18px; width: 100%; transition: border-color .15s, color .15s;
}
div.stButton > button:hover { border-color: var(--accent); color: var(--accent); }
[data-testid="stDataFrame"] { border-radius: var(--r) !important; }
.stTextInput input, .stSelectbox > div > div, .stMultiSelect > div {
    background: var(--surface-2) !important;
    border-color: var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--text-hi) !important;
    font-family: var(--mono) !important;
    font-size: 13px !important;
}
.stCheckbox label {
    font-family: var(--mono) !important;
    font-size: 12px !important;
    color: var(--text-mid) !important;
}
.stExpander {
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    background: var(--surface) !important;
}
label[data-testid="stWidgetLabel"] {
    font-family: var(--mono) !important;
    font-size: 11px !important;
    color: var(--text-lo) !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
</style>
""", unsafe_allow_html=True)


# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def sec(title: str) -> None:
    st.markdown(f"<div class='sec-head'>{title}</div>", unsafe_allow_html=True)


def chip(signal: str) -> str:
    css = {"BUY": "buy", "SELL": "sell"}.get(signal, "hold")
    return f"<span class='chip {css}'>{signal}</span>"


def kpi(label: str, value: str, colour: str = "") -> None:
    st.markdown(
        f"<div class='kpi-card'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-val {colour}'>{value}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_explainer(sig: str) -> None:
    edu = INDICATOR_EXPLAINERS.get(sig)
    if not edu:
        return
    rules_html = "".join(
        f"<div class='rule-row'>"
        f"<span class='rule-cond'>{cond}</span>"
        f"{chip(action)}"
        f"</div>"
        for cond, action in edu["rules"]
    )
    st.markdown(
        f"<div class='explainer'>"
        f"<div class='explainer-name'>{edu['name']}</div>"
        f"<div class='explainer-body'>{edu['body']}</div>"
        f"<div style='margin-top:14px;'>{rules_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ===========================================================================
# PAGE HEADER  (perfectly centered)
# ===========================================================================
updated_str = st.session_state.last_updated or "not yet run"
live_html = (
    f"<span class='live-badge'><span class='live-dot'></span>"
    f"Live  ·  refresh #{refresh_count}</span>"
    if st.session_state.analysis_run else ""
)

st.markdown(
    f"<div class='page-header'>"
    f"<div class='page-title'>Stock Quant Analysis Dashboard{live_html}</div>"
    f"<div class='page-desc'>"
    "This dashboard analyses stock market data using technical indicators and trading "
    "strategies, then runs a backtest to evaluate each strategy's historical performance."
    "</div>"
    f"<div class='page-meta'>Last updated: {updated_str}</div>"
    f"</div>",
    unsafe_allow_html=True,
)

# ===========================================================================
# STRATEGY FLASHCARDS  —  education panel shown before controls
# ===========================================================================
FLASHCARDS = [
    {
        "name":  "Moving Average",
        "desc":  "Detects trend direction by comparing two average price lines over time.",
        "rules": "SMA 20 > EMA 20  →  BUY\nSMA 20 < EMA 20  →  SELL",
    },
    {
        "name":  "RSI",
        "desc":  "Measures whether a stock is overbought or oversold on a 0–100 scale.",
        "rules": "RSI < 30  →  BUY  (oversold)\nRSI > 70  →  SELL  (overbought)",
    },
    {
        "name":  "MACD",
        "desc":  "Detects momentum changes by tracking two exponential moving averages.",
        "rules": "MACD crosses above signal  →  BUY\nMACD crosses below signal  →  SELL",
    },
    {
        "name":  "Bollinger Bands",
        "desc":  "Shows price volatility. Wide bands mean high volatility; narrow means low.",
        "rules": "Price near lower band  →  BUY\nPrice near upper band  →  SELL",
    },
    {
        "name":  "EMA Crossover",
        "desc":  "Compares a fast and a slow exponential average to spot momentum shifts.",
        "rules": "EMA 12 > EMA 26  →  BUY\nEMA 12 < EMA 26  →  SELL",
    },
]

st.markdown(
    "<div class='flashcard-section-label'>Strategy Guide — understand each strategy before running analysis</div>",
    unsafe_allow_html=True,
)

# Row 1 — first 3 cards
fc_row1 = st.columns(3)
for i in range(3):
    with fc_row1[i]:
        card = FLASHCARDS[i]
        st.markdown(
            f"<div class='flashcard'>"
            f"<div class='fc-name'>{card['name']}</div>"
            f"<div class='fc-desc'>{card['desc']}</div>"
            f"<div class='fc-rules'>{card['rules'].replace(chr(10), '<br>')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# Row 2 — last 2 cards (centred via empty padding columns)
_, fc_c1, fc_c2, _ = st.columns([0.5, 1, 1, 0.5])
for col, card in zip([fc_c1, fc_c2], FLASHCARDS[3:]):
    with col:
        st.markdown(
            f"<div class='flashcard'>"
            f"<div class='fc-name'>{card['name']}</div>"
            f"<div class='fc-desc'>{card['desc']}</div>"
            f"<div class='fc-rules'>{card['rules'].replace(chr(10), '<br>')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ===========================================================================
# CONTROL PANEL  —  single row, six columns, no sidebar
# ===========================================================================
col0, col1, col2, col3, col4, col5 = st.columns([1.8, 2, 1.5, 3, 2, 1.5])

with col0:
    market = st.selectbox(
        "Market",
        options=["US Market", "Indian Market (NIFTY 50)"],
        index=["US Market", "Indian Market (NIFTY 50)"].index(
            st.session_state.market
        ),
        key="market_selector",
    )

with col1:
    # Single search input — label is the widget label, value drives suggestions.
    # The selectbox below it shows live Yahoo Finance results as the user types.
    ticker_query = st.text_input(
        "Stock Symbol",
        value="",
        placeholder="Search: AAPL, Tesla, NVD ..." if market == "US Market"
                    else "Search: RELIANCE, TCS, INFY ...",
        key="ticker_query",
        label_visibility="visible",
    )
    suggestions  = fetch_ticker_suggestions(ticker_query, market)

    # Keep the last known symbol selected when it is still in the list
    try:
        default_idx = suggestions.index(st.session_state.last_symbol)
    except ValueError:
        default_idx = 0

    symbol = st.selectbox(
        "Select ticker",
        options=suggestions,
        index=default_idx,
        key="sel_symbol",
        label_visibility="collapsed",   # hides duplicate label; search bar IS the label
    )

with col2:
    timeframe = st.selectbox(
        "Timeframe",
        options=["15m", "30m", "1h", "1d"],
        index=["15m", "30m", "1h", "1d"].index(st.session_state.last_timeframe),
        key="sel_timeframe",
    )
    period = PERIOD_MAP[timeframe]

with col3:
    selected_signals = st.multiselect(
        "Strategies",
        options=list(STRATEGY_LABELS.keys()),
        default=st.session_state.last_signals,
        format_func=lambda x: STRATEGY_LABELS[x],
        key="sel_strategies",
    )

with col4:
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    show_sma = st.checkbox("SMA 20",          value=st.session_state.last_show_sma, key="cb_sma")
    show_ema = st.checkbox("EMA 20",          value=st.session_state.last_show_ema, key="cb_ema")
    show_bb  = st.checkbox("Bollinger Bands", value=st.session_state.last_show_bb,  key="cb_bb")

with col5:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    run_button = st.button("Run Analysis", key="btn_run")

# ===========================================================================
# SAVE SETTINGS ON CLICK
# ===========================================================================
if run_button:
    if not selected_signals:
        st.warning("Select at least one strategy before running analysis.")
        st.stop()
    st.session_state.analysis_run           = True
    st.session_state.market                 = market
    st.session_state.last_symbol            = symbol
    st.session_state.last_timeframe         = timeframe
    st.session_state.last_signals           = selected_signals
    st.session_state.last_show_sma          = show_sma
    st.session_state.last_show_ema          = show_ema
    st.session_state.last_show_bb           = show_bb
    st.session_state.active_chart_strategy  = None

# ===========================================================================
# ANALYSIS PIPELINE  —  runs on click AND every auto-refresh
# ===========================================================================
if st.session_state.analysis_run:

    _sym      = st.session_state.last_symbol
    _tf       = st.session_state.last_timeframe
    _period   = PERIOD_MAP[_tf]
    _sigs     = st.session_state.last_signals
    _show_sma = st.session_state.last_show_sma
    _show_ema = st.session_state.last_show_ema
    _show_bb  = st.session_state.last_show_bb
    _keys     = [SIGNAL_KEY_MAP[s] for s in _sigs]

    # ── Fetch ──
    with st.spinner(f"Fetching {_sym} ({_tf} / {_period}) ..."):
        try:
            df_raw = fetch_stock_data(_sym, _tf, _period)
        except Exception as exc:
            st.error(f"Data fetch failed for {_sym}: {exc}")
            st.stop()
    if df_raw.empty:
        st.error(f"No data returned for {_sym}. Check the symbol and try again.")
        st.stop()

    # ── Indicators + Signals ──
    with st.spinner("Calculating indicators and signals ..."):
        df_ind  = calculate_indicators(df_raw)
        df_sigs = run_strategies(df_ind, _keys)

    # ── Backtesting ──
    with st.spinner("Running backtests ..."):
        bt_rows = []
        for col in _sigs:
            r = backtest(df_sigs, col)
            bt_rows.append({
                "Strategy":         r["strategy"],
                "Final Value ($)":  r["final_value"],
                "Total Return (%)": r["total_return"],
                "Total Trades":     r["total_trades"],
                "Win Rate (%)":     r["win_rate"],
                "Max Drawdown (%)": r["max_drawdown"],
                "Sharpe Ratio":     r["sharpe_ratio"],
                "_trade_log":       r["trade_log"],
            })
        comparison_df = (
            pd.DataFrame(bt_rows)
            .sort_values("Total Return (%)", ascending=False)
            .reset_index(drop=True)
        )

    st.session_state.last_updated = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    # =======================================================================
    # SECTION 1  —  Performance Summary
    # =======================================================================
    st.markdown("---")
    best = comparison_df.iloc[0]

    sec(f"Performance Summary  —  best strategy: {best['Strategy']}")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: kpi("Final Value",  f"${best['Final Value ($)']:,.2f}", "")
    with k2: kpi("Total Return", f"{best['Total Return (%)']:.2f}%",
                 "pos" if best["Total Return (%)"] >= 0 else "neg")
    with k3: kpi("Total Trades", str(int(best["Total Trades"])), "")
    with k4: kpi("Win Rate",     f"{best['Win Rate (%)']:.1f}%",   "pos")
    with k5: kpi("Max Drawdown", f"{best['Max Drawdown (%)']:.2f}%", "neg")
    with k6: kpi("Sharpe Ratio", f"{best['Sharpe Ratio']:.4f}",
                 "pos" if best["Sharpe Ratio"] >= 0 else "neg")

    # =======================================================================
    # SECTION 2  —  Price Chart  (full width)
    # =======================================================================
    st.markdown("---")
    sec("Price Chart")

    # Resolve active chart strategy
    if (
        st.session_state.active_chart_strategy is None
        or st.session_state.active_chart_strategy not in _sigs
    ):
        st.session_state.active_chart_strategy = _sigs[0]

    # Strategy switcher — text buttons, no emojis
    if len(_sigs) > 1:
        st.caption("Select strategy to display:")
        sw_cols = st.columns(len(_sigs))
        for i, sig in enumerate(_sigs):
            with sw_cols[i]:
                active = sig == st.session_state.active_chart_strategy
                label  = f"[ {STRATEGY_LABELS[sig]} ]" if active else STRATEGY_LABELS[sig]
                if st.button(label, key=f"sw_{sig}"):
                    st.session_state.active_chart_strategy = sig

    active_sig = st.session_state.active_chart_strategy

    # Full-width chart
    fig = generate_chart(
        df_sigs,
        strategy_column=active_sig,
        show_sma=_show_sma,
        show_ema=_show_ema,
        show_bb=_show_bb,
        open_in_browser=False,
    )
    fig.update_layout(height=500)
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"main_chart_{active_sig}_{refresh_count}",
    )

    # =======================================================================
    # SECTION 3  —  Backtesting Results
    # =======================================================================
    st.markdown("---")
    sec("Backtesting Results")

    st.markdown(
        f"<p>Simulation: symbol <strong>{_sym}</strong>, "
        f"timeframe <strong>{_tf}</strong>, period <strong>{_period}</strong>, "
        f"initial capital <strong>$10,000</strong>. "
        "Strategies are ranked by total return.</p>",
        unsafe_allow_html=True,
    )

    display_df = comparison_df.drop(columns=["_trade_log"])
    styled = display_df.style.applymap(
        lambda v: "color: #23D18B" if isinstance(v, (int, float)) and v > 0
                  else ("color: #F14C60" if isinstance(v, (int, float)) and v < 0 else ""),
        subset=["Total Return (%)", "Max Drawdown (%)"],
    ).format({
        "Final Value ($)":  "${:,.2f}",
        "Total Return (%)": "{:.2f}%",
        "Win Rate (%)":     "{:.1f}%",
        "Max Drawdown (%)": "{:.2f}%",
        "Sharpe Ratio":     "{:.4f}",
    })
    st.dataframe(
        styled,
        use_container_width=True,
        height=min(180 + len(display_df) * 38, 420),
    )

    st.markdown(
        "<p style='font-size:13px; font-weight:600; margin:20px 0 8px;'>Trade Logs</p>",
        unsafe_allow_html=True,
    )
    for row in bt_rows:
        tl = row["_trade_log"]
        with st.expander(f"{row['Strategy']}  —  {len(tl)} trades", expanded=False):
            if tl.empty:
                st.info("No trades executed for this strategy.")
            else:
                tl_d = tl.copy()
                tl_d["Date"] = tl_d["Date"].astype(str)
                st.dataframe(tl_d, use_container_width=True)

    # =======================================================================
    # SECTION 5  —  Strategy Reference
    # =======================================================================
    st.markdown("---")
    sec("Strategy Reference")

    st.markdown(
        "<p style='margin-bottom:18px;'>"
        "A concise description of the signal logic used by each selected strategy."
        "</p>",
        unsafe_allow_html=True,
    )

    sc_cols = st.columns(min(len(_sigs), 2))
    for i, sig in enumerate(_sigs):
        info = strategies_info[SIGNAL_KEY_MAP[sig]]
        with sc_cols[i % 2]:
            st.markdown(
                f"<div class='strat-card'>"
                f"<div class='strat-name'>{info['name']}</div>"
                f"<div class='strat-desc'>{info['description']}</div>"
                f"<div class='strat-rules'>{info['rules']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

# ===========================================================================
# EMPTY STATE  —  before first run
# ===========================================================================
else:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(
        "<p style='text-align:center; font-size:15px; color:var(--text-mid); "
        "padding:40px 0 12px;'>"
        "Select a stock symbol and strategies in the controls above, "
        "then click <strong>Run Analysis</strong> to begin."
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    f1, f2, f3 = st.columns(3)
    for col, title, desc in [
        (f1, "Price Charts",
         "Interactive candlestick charts with configurable overlays including SMA, "
         "EMA, and Bollinger Bands. Buy and sell signals are plotted directly on the chart."),
        (f2, "Five Trading Strategies",
         "Moving Average, RSI, MACD, Bollinger Bands, and EMA Crossover. Each strategy "
         "is explained in plain language alongside its signals."),
        (f3, "Backtesting Engine",
         "Simulates trading from a $10,000 starting balance. Reports final portfolio "
         "value, total return, win rate, maximum drawdown, and annualised Sharpe ratio."),
    ]:
        with col:
            st.markdown(
                f"<div class='feat-card'>"
                f"<div class='feat-title'>{title}</div>"
                f"<div class='feat-desc'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

# ===========================================================================
# FOOTER
# ===========================================================================
st.markdown(
    "<div class='footer'>"
    "Stock Quant Analysis Dashboard &nbsp;&middot;&nbsp; Final Year CS Project "
    "&nbsp;&middot;&nbsp; Data sourced from Yahoo Finance via yfinance"
    "</div>",
    unsafe_allow_html=True,
)