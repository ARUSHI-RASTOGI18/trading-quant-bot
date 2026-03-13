"""
Stock Quant Analysis Dashboard
dashboard/app.py  —  UI layer only.
Backend modules (data_fetcher, indicators, trading_strategies, backtester,
chart_generator) are imported unchanged.
"""

import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_root = os.path.join(os.path.dirname(__file__), "..")
for _p in ("data", "indicators", "strategies", "backtesting", "dashboard"):
    sys.path.append(os.path.join(_root, _p))

from data_fetcher       import fetch_stock_data          # noqa: E402
from indicators         import calculate_indicators      # noqa: E402
from trading_strategies import run_strategies, strategies_info  # noqa: E402
from backtester         import backtest                  # noqa: E402
from chart_generator    import generate_chart            # noqa: E402

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Stock Quant Analysis Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Auto-refresh — every 30 s while analysis is live
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

POPULAR_TICKERS = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "NFLX"]

INDICATOR_EXPLAINERS = {
    "MA_signal": {
        "name":  "Moving Average (SMA / EMA)",
        "body":  (
            "The Moving Average strategy compares a 20-period Simple Moving Average "
            "(SMA) with a 20-period Exponential Moving Average (EMA). The SMA weights "
            "all periods equally and reacts slowly to price changes. The EMA gives more "
            "weight to recent prices and reacts faster. When the SMA rises above the EMA "
            "the market is trending upward; when it falls below, a downtrend is indicated."
        ),
        "rules": [
            ("SMA 20 > EMA 20", "BUY",  "buy"),
            ("SMA 20 < EMA 20", "SELL", "sell"),
            ("SMA 20 = EMA 20", "HOLD", "hold"),
        ],
    },
    "RSI_signal": {
        "name":  "RSI — Relative Strength Index",
        "body":  (
            "RSI measures the speed and magnitude of recent price changes on a scale "
            "of 0 to 100. A reading below 30 suggests the asset is oversold and may "
            "recover. A reading above 70 suggests the asset is overbought and may "
            "pull back. Between those thresholds the trend is considered neutral."
        ),
        "rules": [
            ("RSI 14 < 30  (oversold)",  "BUY",  "buy"),
            ("RSI 14 > 70  (overbought)", "SELL", "sell"),
            ("30 <= RSI <= 70",            "HOLD", "hold"),
        ],
    },
    "MACD_signal_trade": {
        "name":  "MACD — Moving Average Convergence Divergence",
        "body":  (
            "MACD is computed as EMA(12) minus EMA(26). A 9-period EMA of the MACD "
            "line, called the signal line, is plotted alongside it. When the MACD "
            "crosses above the signal line, bullish momentum is building. When it "
            "crosses below, bearish momentum is taking over."
        ),
        "rules": [
            ("MACD crosses above signal line", "BUY",  "buy"),
            ("MACD crosses below signal line", "SELL", "sell"),
            ("No crossover",                   "HOLD", "hold"),
        ],
    },
    "BB_signal": {
        "name":  "Bollinger Bands",
        "body":  (
            "Bollinger Bands place an upper and lower bound at two standard deviations "
            "above and below a 20-period SMA. Wide bands indicate high volatility; "
            "narrow bands indicate low volatility. Price touching the lower band "
            "suggests the asset may be oversold; touching the upper band suggests "
            "it may be overbought."
        ),
        "rules": [
            ("Close < Lower Band", "BUY",  "buy"),
            ("Close > Upper Band", "SELL", "sell"),
            ("Close between bands", "HOLD", "hold"),
        ],
    },
    "EMA_signal": {
        "name":  "EMA Crossover",
        "body":  (
            "The EMA Crossover strategy uses two exponential moving averages: "
            "EMA(12) as the fast line and EMA(26) as the slow line. When the fast "
            "line crosses above the slow line, short-term momentum is shifting "
            "upward. When it crosses below, momentum is shifting downward."
        ),
        "rules": [
            ("EMA 12 crosses above EMA 26", "BUY",  "buy"),
            ("EMA 12 crosses below EMA 26", "SELL", "sell"),
            ("No crossover",                "HOLD", "hold"),
        ],
    },
}

# ---------------------------------------------------------------------------
# CSS — clean, minimal dark theme, no emojis in style names
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

:root {
    --bg:          #0A0E14;
    --surface:     #0F1620;
    --surface-2:   #141E2B;
    --border:      #1C2B3A;
    --border-2:    #243447;
    --accent:      #3B9EFF;
    --green:       #23D18B;
    --red:         #F14C60;
    --amber:       #E8A838;
    --text-hi:     #E8EDF2;
    --text-mid:    #8899AA;
    --text-lo:     #3D5166;
    --font-body:   'DM Sans', sans-serif;
    --font-mono:   'DM Mono', monospace;
    --radius:      8px;
    --radius-lg:   12px;
}

/* ── Reset / base ── */
html, body, .stApp { background: var(--bg) !important; color: var(--text-hi); font-family: var(--font-body); }
[data-testid="stSidebar"] { display: none !important; }
.block-container { padding: 2rem 2.5rem 4rem !important; max-width: 1400px !important; margin: 0 auto; }
p, li { color: var(--text-mid); font-size: 14px; line-height: 1.7; }
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 2rem 0 !important; }
a { color: var(--accent); text-decoration: none; }

/* ── Page heading ── */
.page-title {
    font-size: clamp(20px, 3vw, 30px);
    font-weight: 600;
    color: var(--text-hi);
    margin: 0 0 6px;
    letter-spacing: -0.3px;
}
.page-desc {
    font-size: 14px;
    color: var(--text-mid);
    margin: 0 0 4px;
    max-width: 720px;
}
.page-meta {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-lo);
}
.live-indicator {
    display: inline-flex; align-items: center; gap: 5px;
    font-family: var(--font-mono); font-size: 11px; color: var(--green);
    background: rgba(35,209,139,.07); border: 1px solid rgba(35,209,139,.2);
    border-radius: 20px; padding: 3px 10px; margin-left: 12px;
    vertical-align: middle;
}
.live-dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: var(--green); animation: blink 2s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.2} }

/* ── Control panel ── */
.ctrl-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px 24px;
    margin: 20px 0;
}
.ticker-suggestions {
    display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px;
}
.ticker-pill {
    font-family: var(--font-mono); font-size: 11px;
    color: var(--accent);
    background: rgba(59,158,255,.07); border: 1px solid rgba(59,158,255,.18);
    border-radius: 4px; padding: 2px 8px;
}

/* ── Section heading ── */
.section-title {
    font-size: 13px; font-weight: 600; letter-spacing: 0.8px;
    text-transform: uppercase; color: var(--text-mid);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px; margin: 32px 0 16px;
}

/* ── KPI cards ── */
.kpi-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 4px; }
.kpi-card {
    flex: 1 1 140px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 16px 18px;
    min-width: 120px;
}
.kpi-label {
    font-family: var(--font-mono); font-size: 10px;
    color: var(--text-lo); text-transform: uppercase;
    letter-spacing: 0.7px; margin-bottom: 8px;
}
.kpi-val {
    font-family: var(--font-mono); font-size: 22px; font-weight: 500;
    color: var(--text-hi);
}
.kpi-val.pos { color: var(--green); }
.kpi-val.neg { color: var(--red); }

/* ── Signal chips ── */
.chip {
    display: inline-block; font-family: var(--font-mono); font-size: 11px;
    border-radius: 4px; padding: 2px 8px; font-weight: 500;
}
.chip.buy  { background: rgba(35,209,139,.1);  color: var(--green); border: 1px solid rgba(35,209,139,.25); }
.chip.sell { background: rgba(241,76,96,.1);   color: var(--red);   border: 1px solid rgba(241,76,96,.25); }
.chip.hold { background: rgba(232,168,56,.1);  color: var(--amber); border: 1px solid rgba(232,168,56,.25); }

/* ── Indicator explainer cards ── */
.explainer {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 18px 20px; margin-bottom: 12px;
    height: 100%;
}
.explainer-name {
    font-size: 13px; font-weight: 600; color: var(--text-hi); margin-bottom: 10px;
}
.explainer-body { font-size: 13px; color: var(--text-mid); line-height: 1.7; }
.rule-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 5px 0; border-top: 1px solid var(--border);
    font-family: var(--font-mono); font-size: 11px;
}
.rule-cond { color: var(--text-mid); }

/* ── Strategy description cards ── */
.strat-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 18px 20px; margin-bottom: 12px;
}
.strat-name { font-size: 14px; font-weight: 600; color: var(--text-hi); margin-bottom: 6px; }
.strat-desc { font-size: 13px; color: var(--text-mid); line-height: 1.6; margin-bottom: 10px; }
.strat-rules { font-family: var(--font-mono); font-size: 11px; color: var(--amber); }

/* ── Signal feed ── */
.signal-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 7px 0; border-bottom: 1px solid var(--border);
    font-size: 13px;
}
.signal-name { color: var(--text-mid); font-family: var(--font-mono); font-size: 12px; }

/* ── Empty / feature cards ── */
.feat-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius-lg); padding: 28px 24px; text-align: left;
}
.feat-card-title { font-size: 14px; font-weight: 600; color: var(--text-hi); margin-bottom: 8px; }
.feat-card-desc  { font-size: 13px; color: var(--text-mid); line-height: 1.6; }

/* ── Footer ── */
.footer {
    text-align: center; padding: 24px 0 8px;
    font-family: var(--font-mono); font-size: 11px; color: var(--text-lo);
    border-top: 1px solid var(--border); margin-top: 48px;
}

/* ── Streamlit widget overrides ── */
div.stButton > button {
    background: var(--surface-2); color: var(--text-hi);
    border: 1px solid var(--border-2); border-radius: var(--radius);
    font-family: var(--font-body); font-size: 13px; font-weight: 500;
    padding: 9px 18px; width: 100%; transition: border-color .15s, color .15s;
}
div.stButton > button:hover { border-color: var(--accent); color: var(--accent); }
div.stButton > button[kind="primary"] {
    background: var(--accent); color: #fff; border-color: var(--accent);
}
[data-testid="stDataFrame"] { border-radius: var(--radius) !important; }
.stTextInput input, .stSelectbox > div > div, .stMultiSelect > div {
    background: var(--surface-2) !important; border-color: var(--border) !important;
    border-radius: var(--radius) !important; color: var(--text-hi) !important;
    font-family: var(--font-mono) !important; font-size: 13px !important;
}
.stCheckbox label { font-family: var(--font-mono) !important; font-size: 12px !important; color: var(--text-mid) !important; }
.stExpander { border: 1px solid var(--border) !important; border-radius: var(--radius) !important; }
label[data-testid="stWidgetLabel"] {
    font-family: var(--font-mono) !important; font-size: 11px !important;
    color: var(--text-lo) !important; text-transform: uppercase; letter-spacing: 0.5px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def section(title: str) -> None:
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)


def kpi_card(label: str, value: str, colour: str = "") -> str:
    """Return HTML for a single KPI card."""
    return (
        f"<div class='kpi-card'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-val {colour}'>{value}</div>"
        f"</div>"
    )


def chip(signal: str) -> str:
    cls = {"BUY": "buy", "SELL": "sell"}.get(signal, "hold")
    return f"<span class='chip {cls}'>{signal}</span>"


def render_explainer(sig: str) -> None:
    edu = INDICATOR_EXPLAINERS.get(sig)
    if not edu:
        return
    rules_html = "".join(
        f"<div class='rule-row'>"
        f"<span class='rule-cond'>{cond}</span>"
        f"{chip(action)}"
        f"</div>"
        for cond, action, _ in edu["rules"]
    )
    st.markdown(
        f"<div class='explainer'>"
        f"<div class='explainer-name'>{edu['name']}</div>"
        f"<div class='explainer-body'>{edu['body']}</div>"
        f"<div style='margin-top:12px;'>{rules_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ============================================================================
# PAGE HEADING
# ============================================================================
updated_str = st.session_state.last_updated or "—"
live_html = (
    f"<span class='live-indicator'><span class='live-dot'></span>Live · refresh #{refresh_count}</span>"
    if st.session_state.analysis_run else ""
)

st.markdown(
    f"<div class='page-title'>Stock Quant Analysis Dashboard{live_html}</div>"
    f"<div class='page-desc'>"
    "This dashboard analyses stock market data using technical indicators and trading "
    "strategies, then runs a backtest to evaluate each strategy's historical performance."
    "</div>"
    f"<div class='page-meta'>Last updated: {updated_str}</div>",
    unsafe_allow_html=True,
)

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ============================================================================
# CONTROL PANEL
# ============================================================================
st.markdown("<div class='ctrl-panel'>", unsafe_allow_html=True)

col_sym, col_tf, col_strat, col_overlay, col_btn = st.columns([2, 1.2, 3, 1.5, 1.2])

with col_sym:
    symbol = st.text_input(
        "Stock Symbol",
        value=st.session_state.last_symbol,
        placeholder="e.g. AAPL",
        key="input_symbol",
    ).upper().strip()
    pills = "".join(f"<span class='ticker-pill'>{t}</span>" for t in POPULAR_TICKERS)
    st.markdown(f"<div class='ticker-suggestions'>{pills}</div>", unsafe_allow_html=True)

with col_tf:
    timeframe = st.selectbox(
        "Timeframe",
        options=["15m", "30m", "1h", "1d"],
        index=["15m", "30m", "1h", "1d"].index(st.session_state.last_timeframe),
        key="sel_timeframe",
    )
    period = PERIOD_MAP[timeframe]

with col_strat:
    selected_signals = st.multiselect(
        "Strategies",
        options=list(STRATEGY_LABELS.keys()),
        default=st.session_state.last_signals,
        format_func=lambda x: STRATEGY_LABELS[x],
        key="sel_strategies",
    )

with col_overlay:
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    show_sma = st.checkbox("SMA 20", value=st.session_state.last_show_sma, key="cb_sma")
    show_ema = st.checkbox("EMA 20", value=st.session_state.last_show_ema, key="cb_ema")
    show_bb  = st.checkbox("Bollinger Bands", value=st.session_state.last_show_bb, key="cb_bb")

with col_btn:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    run_button = st.button("Run Analysis", key="btn_run")

st.markdown("</div>", unsafe_allow_html=True)

# ============================================================================
# SAVE SETTINGS ON BUTTON CLICK
# ============================================================================
if run_button:
    if not selected_signals:
        st.warning("Select at least one strategy before running analysis.")
        st.stop()
    st.session_state.analysis_run           = True
    st.session_state.last_symbol            = symbol
    st.session_state.last_timeframe         = timeframe
    st.session_state.last_signals           = selected_signals
    st.session_state.last_show_sma          = show_sma
    st.session_state.last_show_ema          = show_ema
    st.session_state.last_show_bb           = show_bb
    st.session_state.active_chart_strategy  = None

# ============================================================================
# ANALYSIS PIPELINE  — runs on click AND every auto-refresh
# ============================================================================
if st.session_state.analysis_run:

    _sym      = st.session_state.last_symbol
    _tf       = st.session_state.last_timeframe
    _period   = PERIOD_MAP[_tf]
    _sigs     = st.session_state.last_signals
    _show_sma = st.session_state.last_show_sma
    _show_ema = st.session_state.last_show_ema
    _show_bb  = st.session_state.last_show_bb
    _keys     = [SIGNAL_KEY_MAP[s] for s in _sigs]

    # ── Fetch ──────────────────────────────────────────────────────────────
    with st.spinner(f"Fetching {_sym} data …"):
        try:
            df_raw = fetch_stock_data(_sym, _tf, _period)
        except Exception as exc:
            st.error(f"Data fetch failed for {_sym}: {exc}")
            st.stop()

    if df_raw.empty:
        st.error(f"No data returned for {_sym}. Check the symbol and try again.")
        st.stop()

    # ── Indicators + Signals ───────────────────────────────────────────────
    with st.spinner("Calculating indicators and signals …"):
        df_ind  = calculate_indicators(df_raw)
        df_sigs = run_strategies(df_ind, _keys)

    # ── Backtesting ────────────────────────────────────────────────────────
    with st.spinner("Running backtests …"):
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

    # =========================================================================
    # SECTION 1 — Performance Summary (KPI cards)
    # =========================================================================
    best = comparison_df.iloc[0]

    section(f"Performance Summary — {best['Strategy']} (best strategy)")

    kpi_cols = st.columns(6)
    kpi_items = [
        ("Final Value",   f"${best['Final Value ($)']:,.2f}",    ""),
        ("Total Return",  f"{best['Total Return (%)']:.2f}%",
            "pos" if best["Total Return (%)"] >= 0 else "neg"),
        ("Total Trades",  str(int(best["Total Trades"])),        ""),
        ("Win Rate",      f"{best['Win Rate (%)']:.1f}%",        "pos"),
        ("Max Drawdown",  f"{best['Max Drawdown (%)']:.2f}%",    "neg"),
        ("Sharpe Ratio",  f"{best['Sharpe Ratio']:.4f}",
            "pos" if best["Sharpe Ratio"] >= 0 else "neg"),
    ]
    for (label, value, cls), col in zip(kpi_items, kpi_cols):
        with col:
            st.markdown(kpi_card(label, value, cls), unsafe_allow_html=True)

    # =========================================================================
    # SECTION 2 — Price Chart
    # =========================================================================
    section("Price Chart")

    # Resolve active chart strategy
    if (
        st.session_state.active_chart_strategy is None
        or st.session_state.active_chart_strategy not in _sigs
    ):
        st.session_state.active_chart_strategy = _sigs[0]

    # Strategy switcher buttons — text only, no emojis
    if len(_sigs) > 1:
        st.caption("Select strategy to display on chart:")
        sw_cols = st.columns(len(_sigs))
        for i, sig in enumerate(_sigs):
            with sw_cols[i]:
                is_active = sig == st.session_state.active_chart_strategy
                label = f"[ {STRATEGY_LABELS[sig]} ]" if is_active else STRATEGY_LABELS[sig]
                if st.button(label, key=f"sw_{sig}"):
                    st.session_state.active_chart_strategy = sig

    active_sig = st.session_state.active_chart_strategy

    # Two-column layout: chart (left 68%) + info panel (right 32%)
    chart_col, info_col = st.columns([17, 8])

    with chart_col:
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

    with info_col:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # How this strategy works
        info = strategies_info[SIGNAL_KEY_MAP[active_sig]]
        with st.expander("How this strategy works", expanded=True):
            st.markdown(
                f"<p style='margin:0'>{info['description']}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='font-family:var(--font-mono); font-size:12px; "
                f"color:var(--amber); margin-top:10px;'>{info['rules']}</p>",
                unsafe_allow_html=True,
            )

        # Signal legend
        st.markdown(
            "<p style='font-family:var(--font-mono); font-size:11px; "
            "color:var(--text-lo); margin:16px 0 8px;'>Signal legend</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<span class='chip buy'>BUY</span> &nbsp; "
            "<span class='chip sell'>SELL</span> &nbsp; "
            "<span class='chip hold'>HOLD</span>",
            unsafe_allow_html=True,
        )

        # Latest signal per strategy
        st.markdown(
            "<p style='font-family:var(--font-mono); font-size:11px; "
            "color:var(--text-lo); margin:20px 0 8px;'>Latest signals</p>",
            unsafe_allow_html=True,
        )
        for sig in _sigs:
            latest = df_sigs[sig].iloc[-1]
            st.markdown(
                f"<div class='signal-row'>"
                f"<span class='signal-name'>{STRATEGY_LABELS[sig]}</span>"
                f"{chip(latest)}"
                f"</div>",
                unsafe_allow_html=True,
            )

    # =========================================================================
    # SECTION 3 — Indicator Explanations
    # =========================================================================
    section("Indicator Explanations")

    st.markdown(
        "<p style='margin-bottom:16px;'>"
        "Each selected strategy is powered by one or more technical indicators. "
        "The explanations below describe how each indicator is calculated and "
        "what its signals mean."
        "</p>",
        unsafe_allow_html=True,
    )

    n_cols = min(len(_sigs), 2)
    edu_cols = st.columns(n_cols)
    for i, sig in enumerate(_sigs):
        with edu_cols[i % n_cols]:
            render_explainer(sig)

    # =========================================================================
    # SECTION 4 — Backtesting Results
    # =========================================================================
    section("Backtesting Results")

    st.markdown(
        f"<p>Simulation parameters: symbol <strong>{_sym}</strong>, "
        f"timeframe <strong>{_tf}</strong>, period <strong>{_period}</strong>, "
        f"initial capital <strong>$10,000</strong>.</p>",
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
                st.info("No trades were executed for this strategy.")
            else:
                tl_d = tl.copy()
                tl_d["Date"] = tl_d["Date"].astype(str)
                st.dataframe(tl_d, use_container_width=True)

    # =========================================================================
    # SECTION 5 — Strategy Reference
    # =========================================================================
    section("Strategy Reference")

    st.markdown(
        "<p style='margin-bottom:16px;'>"
        "A summary of the logic applied by each selected strategy."
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

# ============================================================================
# EMPTY STATE — shown before any analysis has been run
# ============================================================================
else:
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:15px; color:var(--text-mid); text-align:center; "
        "padding:40px 0 12px;'>"
        "Enter a stock symbol and select your strategies above, then click "
        "<strong>Run Analysis</strong> to begin."
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    f1, f2, f3 = st.columns(3)
    for col, title, desc in [
        (f1, "Price Charts",
         "Interactive candlestick charts with configurable overlays including "
         "SMA, EMA, and Bollinger Bands. Buy and sell signals are plotted "
         "directly on the chart."),
        (f2, "Five Trading Strategies",
         "Moving Average, RSI, MACD, Bollinger Bands, and EMA Crossover. "
         "Each strategy is explained in plain language alongside its signals."),
        (f3, "Backtesting Engine",
         "Simulates trading from a $10,000 starting balance. Reports final "
         "portfolio value, total return, win rate, maximum drawdown, and "
         "annualised Sharpe ratio."),
    ]:
        with col:
            st.markdown(
                f"<div class='feat-card'>"
                f"<div class='feat-card-title'>{title}</div>"
                f"<div class='feat-card-desc'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

# ============================================================================
# FOOTER
# ============================================================================
st.markdown(
    "<div class='footer'>"
    "Stock Quant Analysis Dashboard &nbsp;&middot;&nbsp; Final Year CS Project "
    "&nbsp;&middot;&nbsp; Data sourced from Yahoo Finance via yfinance"
    "</div>",
    unsafe_allow_html=True,
)