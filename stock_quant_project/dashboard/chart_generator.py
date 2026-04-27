"""
dashboard/chart_generator.py
Generates a clean, beginner-friendly Plotly chart.

Layout  (2 rows, shared x-axis):
  Row 1  Price   — candlestick · optional SMA 20 · optional EMA 20
                   BUY markers (green triangle-up)
                   SELL markers (red triangle-down)
  Row 2  RSI 14  — RSI line · overbought 70 · oversold 30

Intentionally omitted (data still computed by backend, just not drawn):
  - Volume subplot and bars
  - Bollinger Bands (upper line, lower line, shaded fill)
  - MACD subplot
  - "OHLC" / "Volume" / "BB Upper" / "BB Lower" legend entries

Only the visualisation layer is defined here.
Data fetching, indicator calculation, strategy signals, and backtesting
are handled in separate backend modules and are not touched.
"""

import os
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------------
# Colour tokens
# ---------------------------------------------------------------------------
_GREEN   = "#2ECC71"   # BUY markers, up candles
_RED     = "#E74C3C"   # SELL markers, down candles
_AMBER   = "#F5A623"   # SMA 20 line
_BLUE    = "#4A90D9"   # EMA 20 line
_ORANGE  = "#F39C12"   # RSI line

# Background / grid
_BG      = "#0F1117"
_GRID    = "rgba(255, 255, 255, 0.04)"
_ZERO    = "rgba(255, 255, 255, 0.06)"
_TEXT    = "#8B949E"
_TEXT_HI = "#C9D1D9"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_chart(
    df: pd.DataFrame,
    strategy_column: str,
    show_sma: bool = True,
    show_ema: bool = True,
    show_bb: bool = True,       # kept for caller compatibility — not drawn
    open_in_browser: bool = False,
) -> go.Figure:
    """
    Build and return a simplified Plotly figure for the given strategy signal.

    What is drawn
    -------------
    Price panel (row 1):
        Candlestick chart (green up / red down)
        SMA 20 line  — amber dotted   (when show_sma=True and column present)
        EMA 20 line  — blue dashed    (when show_ema=True and column present)
        BUY  signal  — green triangle-up    placed just below each candle low
        SELL signal  — red   triangle-down  placed just above each candle high

    RSI panel (row 2):
        RSI 14 line
        Overbought reference at 70  (dashed red)
        Oversold   reference at 30  (dashed green)

    What is NOT drawn
    -----------------
        Volume bars / subplot
        Bollinger Bands  (show_bb is accepted but silently ignored)
        MACD subplot
        Excess legend entries (Volume, BB Upper, BB Lower, OHLC)

    Args:
        df:               DataFrame produced by calculate_indicators() and
                          run_strategies().  Must contain Date, Open, High,
                          Low, Close and the named strategy_column.
        strategy_column:  Signal column, e.g. "MA_signal".
        show_sma:         Draw SMA_20 overlay when True.
        show_ema:         Draw EMA_20 overlay when True.
        show_bb:          Accepted for API compatibility; Bollinger Bands
                          are not rendered regardless of this value.
        open_in_browser:  If True, call fig.show() before returning.

    Returns:
        plotly.graph_objects.Figure
    """
    if strategy_column not in df.columns:
        raise ValueError(
            f"[chart_generator] Signal column '{strategy_column}' not found."
        )

    print(f"[chart_generator] Building chart — strategy: {strategy_column}")

    # Convert dates to plain strings once — avoids timezone label noise
    dates = df["Date"].astype(str)

    # -----------------------------------------------------------------------
    # Figure skeleton — 2 rows, shared x-axis
    # -----------------------------------------------------------------------
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.72, 0.28],
        subplot_titles=["Price", "RSI  (14)"],
    )

    # =======================================================================
    # ROW 1  —  PRICE
    # =======================================================================

    # Candlestick ─────────────────────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
            increasing_line_color=_GREEN,
            decreasing_line_color=_RED,
            increasing_fillcolor=_GREEN,
            decreasing_fillcolor=_RED,
            showlegend=True,
        ),
        row=1, col=1,
    )

    # SMA 20 ──────────────────────────────────────────────────────────────
    if show_sma and "SMA_20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["SMA_20"],
                mode="lines",
                name="SMA 20",
                line=dict(color=_AMBER, width=1.6, dash="dot"),
                showlegend=True,
            ),
            row=1, col=1,
        )

    # EMA 20 ──────────────────────────────────────────────────────────────
    if show_ema and "EMA_20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["EMA_20"],
                mode="lines",
                name="EMA 20",
                line=dict(color=_BLUE, width=1.6, dash="dash"),
                showlegend=True,
            ),
            row=1, col=1,
        )

    # BUY markers — green triangle-up, just below each candle low ─────────
    buy_mask = df[strategy_column] == "BUY"
    if buy_mask.any():
        fig.add_trace(
            go.Scatter(
                x=dates[buy_mask],
                y=df["Low"][buy_mask] * 0.993,
                mode="markers",
                name="BUY",
                marker=dict(
                    symbol="triangle-up",
                    color=_GREEN,
                    size=14,
                    line=dict(color="white", width=0.8),
                ),
                showlegend=True,
            ),
            row=1, col=1,
        )

    # SELL markers — red triangle-down, just above each candle high ───────
    sell_mask = df[strategy_column].str.startswith("SELL")
    if sell_mask.any():
        fig.add_trace(
            go.Scatter(
                x=dates[sell_mask],
                y=df["High"][sell_mask] * 1.007,
                mode="markers",
                name="SELL",
                marker=dict(
                    symbol="triangle-down",
                    color=_RED,
                    size=14,
                    line=dict(color="white", width=0.8),
                ),
                showlegend=True,
            ),
            row=1, col=1,
        )

    # =======================================================================
    # ROW 2  —  RSI
    # =======================================================================
    if "RSI_14" in df.columns:

        # RSI line ────────────────────────────────────────────────────────
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["RSI_14"],
                mode="lines",
                name="RSI 14",
                line=dict(color=_ORANGE, width=1.6),
                showlegend=False,    # panel title makes it self-evident
            ),
            row=2, col=1,
        )

        # Overbought — 70 ─────────────────────────────────────────────────
        fig.add_hline(
            y=70,
            line_dash="dash",
            line_color="rgba(231, 76, 60, 0.50)",
            row=2, col=1,
            annotation_text="70",
            annotation_position="right",
            annotation_font=dict(size=10, color="rgba(231, 76, 60, 0.75)"),
        )

        # Oversold — 30 ───────────────────────────────────────────────────
        fig.add_hline(
            y=30,
            line_dash="dash",
            line_color="rgba(46, 204, 113, 0.50)",
            row=2, col=1,
            annotation_text="30",
            annotation_position="right",
            annotation_font=dict(size=10, color="rgba(46, 204, 113, 0.75)"),
        )

        # Lock RSI y-axis so the scale never auto-shifts
        fig.update_yaxes(range=[0, 100], row=2, col=1)

    # =======================================================================
    # GLOBAL LAYOUT  —  minimal dark theme
    # =======================================================================
    _strategy_label = strategy_column.replace("_", " ")

    fig.update_layout(
        # Chart title (small, left-aligned, secondary)
        title=dict(
            text=_strategy_label,
            font=dict(size=13, color=_TEXT, family="DM Mono, monospace"),
            x=0.01,
            xanchor="left",
        ),

        # Background
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,

        # Base font
        font=dict(color=_TEXT, size=11, family="DM Mono, monospace"),

        # Legend — horizontal strip, top of price panel, clean entries only
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0, 0, 0, 0)",
            font=dict(size=11, color=_TEXT_HI),
            traceorder="normal",
            itemsizing="constant",
        ),

        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        height=560,
        margin=dict(l=48, r=68, t=56, b=32),
    )

    # Axis styling — minimal grid, no distracting borders
    _axis = dict(
        gridcolor=_GRID,
        zerolinecolor=_ZERO,
        color=_TEXT,
        showgrid=True,
        linecolor=_ZERO,
        tickfont=dict(size=10),
    )
    fig.update_xaxes(**_axis)
    fig.update_yaxes(**_axis)

    # Subplot title font — make panel labels subtle
    for ann in fig.layout.annotations:
        ann.font = dict(size=11, color=_TEXT, family="DM Mono, monospace")

    print("[chart_generator] Chart built successfully.")

    if open_in_browser:
        fig.show()
        print("[chart_generator] Chart opened in browser.")

    return fig


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _root = os.path.join(os.path.dirname(__file__), "..")
    sys.path.append(os.path.join(_root, "data"))
    sys.path.append(os.path.join(_root, "indicators"))
    sys.path.append(os.path.join(_root, "strategies"))

    from data_fetcher       import fetch_stock_data
    from indicators         import calculate_indicators
    from trading_strategies import run_strategies

    _df     = fetch_stock_data("AAPL", "1d", "6mo")
    _df     = calculate_indicators(_df)
    _df     = run_strategies(_df, ["ma", "rsi", "macd", "bb", "ema"])

    _fig = generate_chart(
        _df,
        strategy_column="MA_signal",
        show_sma=True,
        show_ema=True,
        show_bb=True,           # accepted; Bollinger Bands not drawn by design
        open_in_browser=True,
    )

    print(f"\n[chart_generator] Trace count: {len(_fig.data)}")
    for _t in _fig.data:
        print(f"  {_t.name}")