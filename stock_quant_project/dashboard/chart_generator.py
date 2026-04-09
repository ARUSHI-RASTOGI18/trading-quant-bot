import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
COLOUR_SMA      = "#F5A623"   # amber
COLOUR_EMA      = "#4A90D9"   # blue
COLOUR_BB_UPPER = "#9B59B6"   # purple
COLOUR_BB_LOWER = "#9B59B6"   # purple
COLOUR_BB_FILL  = "rgba(155, 89, 182, 0.08)"
COLOUR_BUY      = "#2ECC71"   # green
COLOUR_SELL     = "#E74C3C"   # red


# ---------------------------------------------------------------------------
# Main chart function
# ---------------------------------------------------------------------------

def generate_chart(
    df: pd.DataFrame,
    strategy_column: str,
    show_sma: bool = True,
    show_ema: bool = True,
    show_bb: bool = True,
    open_in_browser: bool = False,
) -> go.Figure:
    """
    Generate an interactive Plotly chart.

    Layout is dynamic based on the active strategy:
      - All strategies : Price (row 1) | RSI (row 2) | Volume (row 3)
      - MACD strategy  : Price (row 1) | RSI (row 2) | MACD (row 3) | Volume (row 4)

    When MACD_signal_trade is active the full MACD panel (line, signal line,
    histogram) is shown in its own subplot so it never overlaps the RSI pane.
    The RSI pane is always shown regardless of strategy.

    Args:
        df:               DataFrame with OHLCV + indicator + signal columns.
        strategy_column:  Signal column name, e.g. "MACD_signal_trade".
        show_sma:         Overlay SMA_20 on price panel.
        show_ema:         Overlay EMA_20 on price panel.
        show_bb:          Overlay Bollinger Bands on price panel.
        open_in_browser:  Call fig.show() to open in the default browser.

    Returns:
        plotly.graph_objects.Figure
    """
    if strategy_column not in df.columns:
        raise ValueError(f"Signal column '{strategy_column}' not found in DataFrame.")

    print(f"[chart_generator] Building chart for strategy: {strategy_column}")

    # Normalise Date column to plain strings for clean x-axis labels
    dates = df["Date"].astype(str)

    # -----------------------------------------------------------------------
    # Decide subplot layout based on active strategy
    # MACD needs a dedicated 4th row; all others use 3 rows.
    # -----------------------------------------------------------------------
    show_macd_panel = (strategy_column == "MACD_signal_trade") and all(
        c in df.columns for c in ("MACD", "MACD_signal", "MACD_hist")
    )

    if show_macd_panel:
        row_heights     = [0.50, 0.18, 0.18, 0.14]
        subplot_titles  = (
            f"Price  ·  {strategy_column}",
            "RSI (14)",
            "MACD",
            "Volume",
        )
        n_rows      = 4
        volume_row  = 4
        macd_row    = 3
        rsi_row     = 2
    else:
        row_heights     = [0.60, 0.20, 0.20]
        subplot_titles  = (
            f"Price  ·  {strategy_column}",
            "RSI (14)",
            "Volume",
        )
        n_rows      = 3
        volume_row  = 3
        macd_row    = None
        rsi_row     = 2

    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
    )

    # -----------------------------------------------------------------------
    # Row 1a — Candlestick
    # -----------------------------------------------------------------------
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="OHLC",
            increasing_line_color="#2ECC71",
            decreasing_line_color="#E74C3C",
            increasing_fillcolor="#2ECC71",
            decreasing_fillcolor="#E74C3C",
        ),
        row=1, col=1,
    )

    # -----------------------------------------------------------------------
    # Row 1b — SMA_20 overlay
    # -----------------------------------------------------------------------
    if show_sma and "SMA_20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["SMA_20"],
                mode="lines",
                name="SMA 20",
                line=dict(color=COLOUR_SMA, width=1.5, dash="dot"),
            ),
            row=1, col=1,
        )

    # -----------------------------------------------------------------------
    # Row 1c — EMA_20 overlay
    # -----------------------------------------------------------------------
    if show_ema and "EMA_20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["EMA_20"],
                mode="lines",
                name="EMA 20",
                line=dict(color=COLOUR_EMA, width=1.5, dash="dash"),
            ),
            row=1, col=1,
        )

    # -----------------------------------------------------------------------
    # Row 1d — Bollinger Bands with filled region
    # -----------------------------------------------------------------------
    if show_bb and "BB_upper" in df.columns and "BB_lower" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["BB_upper"],
                mode="lines",
                name="BB Upper",
                line=dict(color=COLOUR_BB_UPPER, width=1, dash="dot"),
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["BB_lower"],
                mode="lines",
                name="BB Lower",
                line=dict(color=COLOUR_BB_LOWER, width=1, dash="dot"),
                fill="tonexty",
                fillcolor=COLOUR_BB_FILL,
            ),
            row=1, col=1,
        )

    # -----------------------------------------------------------------------
    # Row 1e — BUY markers (green triangle-up)
    # -----------------------------------------------------------------------
    buy_mask = df[strategy_column] == "BUY"
    if buy_mask.any():
        fig.add_trace(
            go.Scatter(
                x=dates[buy_mask],
                y=df["Low"][buy_mask] * 0.995,
                mode="markers",
                name="BUY",
                marker=dict(
                    symbol="triangle-up",
                    color=COLOUR_BUY,
                    size=12,
                    line=dict(color="white", width=0.8),
                ),
            ),
            row=1, col=1,
        )

    # -----------------------------------------------------------------------
    # Row 1f — SELL markers (red triangle-down)
    # -----------------------------------------------------------------------
    sell_mask = df[strategy_column].str.startswith("SELL")
    if sell_mask.any():
        fig.add_trace(
            go.Scatter(
                x=dates[sell_mask],
                y=df["High"][sell_mask] * 1.005,
                mode="markers",
                name="SELL",
                marker=dict(
                    symbol="triangle-down",
                    color=COLOUR_SELL,
                    size=12,
                    line=dict(color="white", width=0.8),
                ),
            ),
            row=1, col=1,
        )

    # -----------------------------------------------------------------------
    # Row rsi_row — RSI subplot (always shown)
    # -----------------------------------------------------------------------
    if "RSI_14" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["RSI_14"],
                mode="lines",
                name="RSI 14",
                line=dict(color="#F39C12", width=1.5),
            ),
            row=rsi_row, col=1,
        )
        # Overbought / oversold reference lines
        for level, label, colour in [
            (70, "Overbought", "rgba(231,76,60,0.5)"),
            (30, "Oversold",   "rgba(46,204,113,0.5)"),
        ]:
            fig.add_hline(
                y=level,
                line_dash="dash",
                line_color=colour,
                row=rsi_row, col=1,
                annotation_text=label,
                annotation_position="right",
            )
        fig.update_yaxes(range=[0, 100], row=rsi_row, col=1)

    # -----------------------------------------------------------------------
    # Row macd_row — MACD subplot (only when MACD strategy is active)
    # -----------------------------------------------------------------------
    if show_macd_panel:
        # MACD line
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["MACD"],
                mode="lines",
                name="MACD",
                line=dict(color="#3B9EFF", width=1.5),
            ),
            row=macd_row, col=1,
        )
        # Signal line
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["MACD_signal"],
                mode="lines",
                name="Signal",
                line=dict(color="#F5A623", width=1.5, dash="dash"),
            ),
            row=macd_row, col=1,
        )
        # Histogram bars — green when positive, red when negative
        hist_colours = [
            "#2ECC71" if v >= 0 else "#E74C3C"
            for v in df["MACD_hist"].fillna(0)
        ]
        fig.add_trace(
            go.Bar(
                x=dates,
                y=df["MACD_hist"],
                name="Histogram",
                marker_color=hist_colours,
                opacity=0.6,
            ),
            row=macd_row, col=1,
        )
        # Zero reference line
        fig.add_hline(
            y=0,
            line_dash="dot",
            line_color="rgba(255,255,255,0.15)",
            row=macd_row, col=1,
        )

    # -----------------------------------------------------------------------
    # Volume bars (last row)
    # -----------------------------------------------------------------------
    volume_colours = [
        COLOUR_BUY if c >= o else COLOUR_SELL
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=dates,
            y=df["Volume"],
            name="Volume",
            marker_color=volume_colours,
            opacity=0.6,
        ),
        row=volume_row, col=1,
    )

    # -----------------------------------------------------------------------
    # Layout styling
    # -----------------------------------------------------------------------
    chart_height = 950 if show_macd_panel else 850

    fig.update_layout(
        title=dict(
            text=f"<b>Stock Quant Analysis Dashboard</b>  ·  {strategy_column}",
            font=dict(size=18, color="white"),
            x=0.5,
        ),
        paper_bgcolor="#0F1117",
        plot_bgcolor="#161B22",
        font=dict(color="#C9D1D9", size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        ),
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        height=chart_height,
        margin=dict(l=50, r=30, t=80, b=40),
        bargap=0.1,
    )

    axis_style = dict(
        gridcolor="#21262D",
        zerolinecolor="#21262D",
        color="#8B949E",
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)

    print("[chart_generator] Chart built successfully.")

    if open_in_browser:
        fig.show()
        print("[chart_generator] Chart opened in browser.")

    return fig


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    project_root = os.path.join(os.path.dirname(__file__), "..")
    sys.path.append(os.path.join(project_root, "data"))
    sys.path.append(os.path.join(project_root, "indicators"))
    sys.path.append(os.path.join(project_root, "strategies"))

    from data_fetcher       import fetch_stock_data
    from indicators         import calculate_indicators
    from trading_strategies import run_strategies

    # 1. Fetch
    raw_df = fetch_stock_data("AAPL", "1d", "6mo")

    # 2. Indicators
    df_ind = calculate_indicators(raw_df)

    # 3. Strategies
    df_signals = run_strategies(df_ind, ["ma", "rsi", "macd", "bb", "ema"])

    # 4. Generate chart for MA_signal and open in browser
    fig = generate_chart(
        df_signals,
        strategy_column="MA_signal",
        show_sma=True,
        show_ema=True,
        show_bb=True,
        open_in_browser=True,
    )

    print(f"\n[chart_generator] Figure contains {len(fig.data)} traces.")