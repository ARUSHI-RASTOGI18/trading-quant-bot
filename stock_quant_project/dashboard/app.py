import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------------------------
# Path setup — allow imports from sibling packages
# ---------------------------------------------------------------------------
project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(os.path.join(project_root, "data"))
sys.path.append(os.path.join(project_root, "indicators"))
sys.path.append(os.path.join(project_root, "strategies"))
sys.path.append(os.path.join(project_root, "backtesting"))
sys.path.append(os.path.join(project_root, "dashboard"))

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
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Auto-refresh every 30 seconds
# ---------------------------------------------------------------------------
refresh_count = st_autorefresh(interval=30000, key="autorefresh")

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "analysis_run" not in st.session_state:
    st.session_state.analysis_run = False

if "last_symbol"   not in st.session_state:
    st.session_state.last_symbol   = "AAPL"

if "last_timeframe" not in st.session_state:
    st.session_state.last_timeframe = "1d"

if "last_signals"  not in st.session_state:
    st.session_state.last_signals  = ["MA_signal", "MACD_signal_trade", "EMA_signal"]

if "last_show_sma" not in st.session_state:
    st.session_state.last_show_sma = True

if "last_show_ema" not in st.session_state:
    st.session_state.last_show_ema = True

if "last_show_bb"  not in st.session_state:
    st.session_state.last_show_bb  = True

if "last_updated"  not in st.session_state:
    st.session_state.last_updated  = None

if "active_chart_strategy" not in st.session_state:
    st.session_state.active_chart_strategy = None

# ---------------------------------------------------------------------------
# Custom CSS — dark, professional styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0F1117; color: #C9D1D9; }
    [data-testid="stSidebar"] { background-color: #161B22; }

    .section-header {
        background: linear-gradient(90deg, #1F2937, #161B22);
        border-left: 4px solid #4A90D9;
        padding: 10px 16px;
        border-radius: 4px;
        margin: 20px 0 12px 0;
        font-size: 18px;
        font-weight: 600;
        color: #E6EDF3;
    }
    .metric-card {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-label   { font-size: 12px; color: #8B949E; margin-bottom: 4px; }
    .metric-value   { font-size: 22px; font-weight: 700; color: #E6EDF3; }
    .metric-positive { color: #2ECC71; }
    .metric-negative { color: #E74C3C; }

    .strategy-card  {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 10px;
    }
    .strategy-name  { font-size: 15px; font-weight: 600; color: #4A90D9; }
    .strategy-desc  { font-size: 13px; color: #8B949E; margin: 6px 0; }
    .strategy-rules { font-size: 12px; color: #F5A623; font-style: italic; }

    div.stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #1A56DB, #4A90D9);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 12px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #1648C0, #3A80C9);
    }
    [data-testid="stDataFrame"] { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Analysis Controls")
    st.markdown("---")

    symbol = st.text_input(
        "📌 Stock Symbol",
        value=st.session_state.last_symbol,
        help="Enter any valid Yahoo Finance ticker, e.g. AAPL, TSLA, MSFT",
    ).upper().strip()

    timeframe = st.selectbox(
        "⏱ Timeframe",
        options=["15m", "30m", "1h", "1d"],
        index=["15m", "30m", "1h", "1d"].index(st.session_state.last_timeframe),
        help="Candle interval for the chart",
    )

    period_map = {"15m": "5d", "30m": "1mo", "1h": "3mo", "1d": "6mo"}
    period = period_map[timeframe]

    st.markdown("---")
    st.markdown("**📊 Select Strategies**")

    strategy_options = {
        "MA_signal":         "Moving Average",
        "RSI_signal":        "RSI",
        "MACD_signal_trade": "MACD",
        "BB_signal":         "Bollinger Bands",
        "EMA_signal":        "EMA Crossover",
    }

    selected_signals = st.multiselect(
        "Strategies to run:",
        options=list(strategy_options.keys()),
        default=st.session_state.last_signals,
        format_func=lambda x: strategy_options[x],
    )

    st.markdown("---")
    st.markdown("**🎨 Chart Overlays**")
    show_sma = st.checkbox("SMA 20",          value=st.session_state.last_show_sma)
    show_ema = st.checkbox("EMA 20",          value=st.session_state.last_show_ema)
    show_bb  = st.checkbox("Bollinger Bands", value=st.session_state.last_show_bb)

    st.markdown("---")
    run_button = st.button("🚀 Run Analysis")

    # Auto-refresh status badge
    st.markdown("---")
    st.markdown("**🔄 Auto-Refresh**")
    status_colour = "#2ECC71" if st.session_state.analysis_run else "#8B949E"
    status_text   = "Active — chart updates live" if st.session_state.analysis_run else "Click Run Analysis to start"
    st.markdown(
        f"<div style='background:#161B22; border:1px solid #30363D; border-radius:6px;"
        f"padding:10px; font-size:12px; color:#8B949E;'>"
        f"⏱ Every <strong style='color:#4A90D9;'>30 seconds</strong><br>"
        f"🔁 Refresh #: <strong style='color:#2ECC71;'>{refresh_count}</strong><br>"
        f"⚡ Status: <strong style='color:{status_colour};'>{status_text}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# When Run Analysis button is clicked — save everything to session_state
# ---------------------------------------------------------------------------
if run_button:
    if not selected_signals:
        st.warning("⚠️ Please select at least one strategy before running analysis.")
        st.stop()

    # Persist user selections so auto-refresh uses the same settings
    st.session_state.analysis_run    = True
    st.session_state.last_symbol     = symbol
    st.session_state.last_timeframe  = timeframe
    st.session_state.last_signals    = selected_signals
    st.session_state.last_show_sma   = show_sma
    st.session_state.last_show_ema   = show_ema
    st.session_state.last_show_bb    = show_bb


# ---------------------------------------------------------------------------
# Analysis pipeline — runs on button click AND on every auto-refresh
# ---------------------------------------------------------------------------
if st.session_state.analysis_run:

    # Use session_state values so refresh always uses the last confirmed settings
    _symbol          = st.session_state.last_symbol
    _timeframe       = st.session_state.last_timeframe
    _period          = period_map[_timeframe]
    _selected_signals = st.session_state.last_signals
    _show_sma        = st.session_state.last_show_sma
    _show_ema        = st.session_state.last_show_ema
    _show_bb         = st.session_state.last_show_bb

    signal_to_key = {
        "MA_signal":         "ma",
        "RSI_signal":        "rsi",
        "MACD_signal_trade": "macd",
        "BB_signal":         "bb",
        "EMA_signal":        "ema",
    }
    strategy_keys = [signal_to_key[s] for s in _selected_signals]

    # -----------------------------------------------------------------------
    # Pipeline execution
    # -----------------------------------------------------------------------
    with st.spinner(f"Fetching {_symbol} data ({_timeframe} / {_period})…"):
        try:
            df_raw = fetch_stock_data(_symbol, _timeframe, _period)
        except Exception as e:
            st.error(f"❌ Failed to fetch data for **{_symbol}**: {e}")
            st.stop()

    if df_raw.empty:
        st.error(f"❌ No data returned for **{_symbol}**. Check the symbol and try again.")
        st.stop()

    with st.spinner("Calculating indicators…"):
        df_ind = calculate_indicators(df_raw)

    with st.spinner("Running strategies…"):
        df_signals = run_strategies(df_ind, strategy_keys)

    with st.spinner("Running backtests…"):
        backtest_results = []
        for col in _selected_signals:
            r = backtest(df_signals, col)
            backtest_results.append({
                "Strategy":         r["strategy"],
                "Final Value ($)":  r["final_value"],
                "Total Return (%)": r["total_return"],
                "Total Trades":     r["total_trades"],
                "Win Rate (%)":     r["win_rate"],
                "Max Drawdown (%)": r["max_drawdown"],
                "Sharpe Ratio":     r["sharpe_ratio"],
                "_trade_log":       r["trade_log"],   # kept for expanders below
            })
        comparison_df = (
            pd.DataFrame(backtest_results)
            .sort_values("Total Return (%)", ascending=False)
            .reset_index(drop=True)
        )

    # Record timestamp of this refresh
    st.session_state.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    st.markdown(
        "<h1 style='text-align:center; color:#E6EDF3;'>📈 Stock Quant Analysis Dashboard</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='text-align:center; color:#8B949E;'>"
        f"Quantitative trading signals · Technical indicators · Backtesting engine<br>"
        f"<span style='font-size:12px;'>🕐 Last updated: {st.session_state.last_updated}"
        f" &nbsp;|&nbsp; Symbol: <strong>{_symbol}</strong>"
        f" &nbsp;|&nbsp; Timeframe: <strong>{_timeframe}</strong></span>"
        f"</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # -----------------------------------------------------------------------
    # KPI strip — best strategy
    # -----------------------------------------------------------------------
    best        = comparison_df.iloc[0]
    ret_colour  = "metric-positive" if best["Total Return (%)"] >= 0 else "metric-negative"
    shr_colour  = "metric-positive" if best["Sharpe Ratio"]     >= 0 else "metric-negative"

    st.markdown(
        f"<div class='section-header'>🏆 Best Strategy: {best['Strategy']}</div>",
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    kpi_data = [
        (k1, "Final Value",  f"${best['Final Value ($)']:,.2f}",      ""),
        (k2, "Total Return", f"{best['Total Return (%)']:.2f}%",       ret_colour),
        (k3, "Total Trades", str(int(best["Total Trades"])),           ""),
        (k4, "Win Rate",     f"{best['Win Rate (%)']:.1f}%",           "metric-positive"),
        (k5, "Max Drawdown", f"{best['Max Drawdown (%)']:.2f}%",       "metric-negative"),
        (k6, "Sharpe Ratio", f"{best['Sharpe Ratio']:.4f}",            shr_colour),
    ]
    for col, label, value, colour in kpi_data:
        with col:
            st.markdown(
                f"<div class='metric-card'>"
                f"<div class='metric-label'>{label}</div>"
                f"<div class='metric-value {colour}'>{value}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------------------------
    # SECTION 1 — Chart
    # -----------------------------------------------------------------------
    st.markdown(
        "<div class='section-header'>📊 Section 1 — Price Chart</div>",
        unsafe_allow_html=True,
    )

    # Set default active chart strategy on first run or if previous selection
    # is no longer in the selected list (e.g. user deselected it)
    if (
        st.session_state.active_chart_strategy is None
        or st.session_state.active_chart_strategy not in _selected_signals
    ):
        st.session_state.active_chart_strategy = _selected_signals[0]

    # Strategy switcher buttons (only shown when multiple strategies selected)
    if len(_selected_signals) > 1:
        st.caption("💡 Switch the chart strategy:")
        chart_cols = st.columns(len(_selected_signals))
        for i, sig in enumerate(_selected_signals):
            with chart_cols[i]:
                # Highlight the currently active strategy button
                label = f"✅ {strategy_options[sig]}" if sig == st.session_state.active_chart_strategy else strategy_options[sig]
                if st.button(label, key=f"chart_btn_{sig}"):
                    st.session_state.active_chart_strategy = sig

    # Always render one chart using the active strategy — single unique key prevents
    # the StreamlitDuplicateElementId error on auto-refresh and strategy switches
    active_strategy = st.session_state.active_chart_strategy
    fig = generate_chart(
        df_signals,
        strategy_column=active_strategy,
        show_sma=_show_sma,
        show_ema=_show_ema,
        show_bb=_show_bb,
        open_in_browser=False,
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"main_chart_{active_strategy}_{refresh_count}",
    )

    # -----------------------------------------------------------------------
    # SECTION 2 — Backtest Results
    # -----------------------------------------------------------------------
    st.markdown(
        "<div class='section-header'>📋 Section 2 — Backtest Results</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"Initial capital: **$10,000**  ·  Symbol: **{_symbol}**  ·  "
        f"Timeframe: **{_timeframe}**  ·  Period: **{_period}**"
    )

    # Display table (drop internal _trade_log column first)
    display_df = comparison_df.drop(columns=["_trade_log"])
    styled = display_df.style.applymap(
        lambda v: "color: #2ECC71" if isinstance(v, (int, float)) and v > 0
                  else ("color: #E74C3C" if isinstance(v, (int, float)) and v < 0 else ""),
        subset=["Total Return (%)", "Max Drawdown (%)"],
    ).format({
        "Final Value ($)":  "${:,.2f}",
        "Total Return (%)": "{:.2f}%",
        "Win Rate (%)":     "{:.1f}%",
        "Max Drawdown (%)": "{:.2f}%",
        "Sharpe Ratio":     "{:.4f}",
    })
    st.dataframe(styled, use_container_width=True,
                 height=min(200 + len(display_df) * 35, 450))

    # Trade logs in expanders
    st.markdown("##### 📝 Trade Logs")
    for row in backtest_results:
        tl = row["_trade_log"]
        with st.expander(f"Trade log — {row['Strategy']}  ({len(tl)} entries)"):
            if tl.empty:
                st.info("No trades were executed for this strategy.")
            else:
                tl_display = tl.copy()
                tl_display["Date"] = tl_display["Date"].astype(str)
                st.dataframe(tl_display, use_container_width=True)

    # -----------------------------------------------------------------------
    # SECTION 3 — Strategy Descriptions
    # -----------------------------------------------------------------------
    st.markdown(
        "<div class='section-header'>📚 Section 3 — Strategy Descriptions</div>",
        unsafe_allow_html=True,
    )

    key_map = {
        "MA_signal":         "ma",
        "RSI_signal":        "rsi",
        "MACD_signal_trade": "macd",
        "BB_signal":         "bb",
        "EMA_signal":        "ema",
    }
    for sig in _selected_signals:
        info = strategies_info[key_map[sig]]
        st.markdown(
            f"<div class='strategy-card'>"
            f"<div class='strategy-name'>📌 {info['name']}</div>"
            f"<div class='strategy-desc'>{info['description']}</div>"
            f"<div class='strategy-rules'>Rules: {info['rules']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Empty state — only shown before the very first Run Analysis click
# ---------------------------------------------------------------------------
else:
    st.markdown(
        "<h1 style='text-align:center; color:#E6EDF3;'>📈 Stock Quant Analysis Dashboard</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#8B949E;'>"
        "Quantitative trading signals · Technical indicators · Backtesting engine</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    st.markdown("""
    <div style='text-align:center; padding: 60px 20px; color: #8B949E;'>
        <div style='font-size: 64px;'>📈</div>
        <h3 style='color: #E6EDF3; margin-top: 16px;'>Ready to Analyse</h3>
        <p>Configure your symbol, timeframe and strategies in the sidebar,<br>
        then click <strong style='color:#4A90D9;'>🚀 Run Analysis</strong> to begin.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col, icon, title, desc in [
        (c1, "🕯️", "Candlestick Charts",   "Interactive Plotly charts with BUY/SELL markers and indicator overlays."),
        (c2, "⚙️", "5 Trading Strategies", "MA Crossover · RSI · MACD · Bollinger Bands · EMA Crossover."),
        (c3, "📊", "Backtesting Engine",    "Simulates trades from $10,000 and reports return, win rate, drawdown and Sharpe ratio."),
    ]:
        with col:
            st.markdown(
                f"<div class='metric-card' style='padding:24px;'>"
                f"<div style='font-size:32px; margin-bottom:10px;'>{icon}</div>"
                f"<div style='font-weight:600; color:#E6EDF3; margin-bottom:8px;'>{title}</div>"
                f"<div style='font-size:13px; color:#8B949E;'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#484F58; font-size:12px;'>"
    "Stock Quant Analysis Dashboard · Final Year CS Project · "
    "Data sourced from Yahoo Finance via yfinance"
    "</p>",
    unsafe_allow_html=True,
)