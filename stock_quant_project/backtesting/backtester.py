import pandas as pd
import numpy as np
import sys
import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INITIAL_CAPITAL = 10_000.0


# ---------------------------------------------------------------------------
# Core backtest engine
# ---------------------------------------------------------------------------

def backtest(df: pd.DataFrame, signal_col: str) -> dict:
    """
    Simulate trading on a single strategy signal column.

    Args:
        df:         DataFrame containing 'Date', 'Close', and the signal column.
        signal_col: Name of the signal column, e.g. "MA_signal".

    Returns:
        dict with keys:
            strategy        - signal column name
            final_value     - final portfolio value (USD)
            total_return    - percentage return
            total_trades    - number of completed round-trips
            win_rate        - percentage of profitable trades
            max_drawdown    - maximum peak-to-trough drawdown (%)
            sharpe_ratio    - annualised Sharpe ratio (risk-free = 0)
            trade_log       - DataFrame of individual trades
    """
    if signal_col not in df.columns:
        raise ValueError(f"Column '{signal_col}' not found in DataFrame.")

    print(f"\n[Backtester] Running backtest for: {signal_col}")

    cash             = INITIAL_CAPITAL
    shares           = 0.0
    buy_price        = 0.0
    trade_log        = []
    portfolio_values = []

    for _, row in df.iterrows():
        signal = row[signal_col]
        price  = row["Close"]
        date   = row["Date"]

        # Track daily portfolio value BEFORE acting on today's signal
        portfolio_values.append(cash + shares * price)

        if signal == "BUY" and cash > 0:
            shares    = cash / price
            buy_price = price
            cash      = 0.0
            trade_log.append({
                "Date":   date,
                "Action": "BUY",
                "Price":  round(price, 4),
                "Shares": round(shares, 4),
                "Profit": None,
            })

        elif signal == "SELL" and shares > 0:
            proceeds = shares * price
            profit   = round(proceeds - (shares * buy_price), 4)
            cash     = proceeds
            trade_log.append({
                "Date":   date,
                "Action": "SELL",
                "Price":  round(price, 4),
                "Shares": round(shares, 4),
                "Profit": profit,
            })
            shares = 0.0

    # Liquidate any open position at the last available close
    if shares > 0:
        last_price = df["Close"].iloc[-1]
        last_date  = df["Date"].iloc[-1]
        proceeds   = shares * last_price
        profit     = round(proceeds - (shares * buy_price), 4)
        cash       = proceeds
        trade_log.append({
            "Date":   last_date,
            "Action": "SELL (close)",
            "Price":  round(last_price, 4),
            "Shares": round(shares, 4),
            "Profit": profit,
        })

    # -----------------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------------
    final_value  = round(cash, 2)
    total_return = round(((final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100, 2)

    trade_df    = pd.DataFrame(trade_log)
    sell_trades = (
        trade_df[trade_df["Action"].str.startswith("SELL")]
        if not trade_df.empty else pd.DataFrame()
    )
    total_trades = len(sell_trades)
    win_rate     = 0.0
    if total_trades > 0:
        wins     = sell_trades[sell_trades["Profit"] > 0]
        win_rate = round((len(wins) / total_trades) * 100, 2)

    # Maximum drawdown (peak-to-trough as a percentage)
    pv_series   = pd.Series(portfolio_values)
    rolling_max = pv_series.cummax()
    drawdown    = (pv_series - rolling_max) / rolling_max * 100
    max_drawdown = round(drawdown.min(), 2)

    # Annualised Sharpe ratio (risk-free rate = 0)
    daily_returns = pv_series.pct_change().dropna()
    if daily_returns.std() != 0:
        sharpe_ratio = round(
            (daily_returns.mean() / daily_returns.std()) * np.sqrt(252), 4
        )
    else:
        sharpe_ratio = 0.0

    # -----------------------------------------------------------------------
    # Print summary
    # -----------------------------------------------------------------------
    print(f"  Final Portfolio Value : ${final_value:,.2f}")
    print(f"  Total Return          : {total_return}%")
    print(f"  Total Trades          : {total_trades}")
    print(f"  Win Rate              : {win_rate}%")
    print(f"  Max Drawdown          : {max_drawdown}%")
    print(f"  Sharpe Ratio          : {sharpe_ratio}")

    if not trade_df.empty:
        print(f"\n  --- Trade Log ({signal_col}) ---")
        print(trade_df.to_string(index=False))

    return {
        "strategy":     signal_col,
        "final_value":  final_value,
        "total_return": total_return,
        "total_trades": total_trades,
        "win_rate":     win_rate,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "trade_log":    trade_df,
    }


# ---------------------------------------------------------------------------
# Multi-strategy comparison runner
# ---------------------------------------------------------------------------

def run_all_backtests(df: pd.DataFrame, signal_columns: list) -> pd.DataFrame:
    """
    Run backtest() for each strategy and return a ranked comparison table.

    Args:
        df:             DataFrame with signal columns already present.
        signal_columns: List of signal column names to backtest.

    Returns:
        pandas DataFrame — one row per strategy, sorted by Total Return descending.
    """
    print("\n" + "=" * 65)
    print("  BACKTESTING ALL STRATEGIES")
    print("=" * 65)

    results = []
    for col in signal_columns:
        if col not in df.columns:
            print(f"[Backtester] WARNING: '{col}' not found — skipping.")
            continue
        r = backtest(df, col)
        results.append({
            "Strategy":         r["strategy"],
            "Final Value ($)":  r["final_value"],
            "Total Return (%)": r["total_return"],
            "Total Trades":     r["total_trades"],
            "Win Rate (%)":     r["win_rate"],
            "Max Drawdown (%)": r["max_drawdown"],
            "Sharpe Ratio":     r["sharpe_ratio"],
        })

    comparison_df = pd.DataFrame(results)
    if not comparison_df.empty:
        comparison_df.sort_values("Total Return (%)", ascending=False, inplace=True)
        comparison_df.reset_index(drop=True, inplace=True)

    return comparison_df


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

    # 3. Signals
    df_signals = run_strategies(df_ind, ["ma", "rsi", "macd", "bb", "ema"])

    # 4. Backtest each strategy
    signal_columns = [
        "MA_signal",
        "RSI_signal",
        "MACD_signal_trade",
        "BB_signal",
        "EMA_signal",
    ]
    comparison = run_all_backtests(df_signals, signal_columns)

    # 5. Print ranked comparison table
    print("\n" + "=" * 65)
    print("  STRATEGY COMPARISON TABLE  (sorted by Total Return)")
    print("=" * 65)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    pd.set_option("display.float_format", "{:.2f}".format)
    print(comparison.to_string(index=False))
    print("=" * 65)