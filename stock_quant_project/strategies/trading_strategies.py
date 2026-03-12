import pandas as pd
import numpy as np
import sys
import os

# ---------------------------------------------------------------------------
# Strategy metadata registry
# ---------------------------------------------------------------------------
strategies_info = {
    "ma": {
        "name": "Moving Average Strategy",
        "description": "Compares SMA_20 and EMA_20 to detect trend direction. "
                       "When the slower SMA rises above the faster EMA the market "
                       "is considered bullish, and vice-versa.",
        "rules": "SMA_20 > EMA_20 → BUY | SMA_20 < EMA_20 → SELL | Else → HOLD",
    },
    "rsi": {
        "name": "RSI Strategy",
        "description": "Detects overbought and oversold market conditions using RSI. "
                       "RSI below 30 signals the asset is oversold (potential reversal up), "
                       "above 70 signals overbought (potential reversal down).",
        "rules": "RSI_14 < 30 → BUY | RSI_14 > 70 → SELL | Else → HOLD",
    },
    "macd": {
        "name": "MACD Strategy",
        "description": "Uses MACD line crossovers with its signal line to identify "
                       "momentum shifts. A bullish crossover triggers a BUY; a bearish "
                       "crossover triggers a SELL.",
        "rules": "MACD crosses above MACD_signal → BUY | MACD crosses below MACD_signal → SELL | Else → HOLD",
    },
    "bb": {
        "name": "Bollinger Band Strategy",
        "description": "Identifies price breakouts relative to volatility bands. "
                       "Price touching the lower band suggests oversold conditions; "
                       "touching the upper band suggests overbought conditions.",
        "rules": "Close < BB_lower → BUY | Close > BB_upper → SELL | Else → HOLD",
    },
    "ema": {
        "name": "EMA Crossover Strategy",
        "description": "Tracks crossovers between EMA_12 and EMA_26 to capture "
                       "short-term momentum shifts. A faster EMA crossing above the "
                       "slower EMA is bullish; crossing below is bearish.",
        "rules": "EMA_12 crosses above EMA_26 → BUY | EMA_12 crosses below EMA_26 → SELL | Else → HOLD",
    },
}


# ---------------------------------------------------------------------------
# Individual strategy functions
# ---------------------------------------------------------------------------

def _strategy_ma(df: pd.DataFrame) -> pd.DataFrame:
    """Moving Average Strategy: SMA_20 vs EMA_20."""
    conditions = [
        df["SMA_20"] > df["EMA_20"],
        df["SMA_20"] < df["EMA_20"],
    ]
    choices = ["BUY", "SELL"]
    df["MA_signal"] = np.select(conditions, choices, default="HOLD")
    return df


def _strategy_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """RSI Strategy: oversold / overbought thresholds."""
    conditions = [
        df["RSI_14"] < 30,
        df["RSI_14"] > 70,
    ]
    choices = ["BUY", "SELL"]
    df["RSI_signal"] = np.select(conditions, choices, default="HOLD")
    return df


def _strategy_macd(df: pd.DataFrame) -> pd.DataFrame:
    """MACD crossover strategy."""
    macd      = df["MACD"]
    macd_sig  = df["MACD_signal"]

    # Crossover detection: compare current vs previous bar relationship
    prev_macd     = macd.shift(1)
    prev_macd_sig = macd_sig.shift(1)

    bullish_cross = (prev_macd <= prev_macd_sig) & (macd > macd_sig)
    bearish_cross = (prev_macd >= prev_macd_sig) & (macd < macd_sig)

    conditions = [bullish_cross, bearish_cross]
    choices    = ["BUY", "SELL"]
    df["MACD_signal_trade"] = np.select(conditions, choices, default="HOLD")
    return df


def _strategy_bb(df: pd.DataFrame) -> pd.DataFrame:
    """Bollinger Band Strategy: price vs bands."""
    conditions = [
        df["Close"] < df["BB_lower"],
        df["Close"] > df["BB_upper"],
    ]
    choices = ["BUY", "SELL"]
    df["BB_signal"] = np.select(conditions, choices, default="HOLD")
    return df


def _strategy_ema(df: pd.DataFrame) -> pd.DataFrame:
    """EMA Crossover Strategy: EMA_12 vs EMA_26."""
    # Derive EMA_12 and EMA_26 from Close if not already present
    if "EMA_12" not in df.columns:
        df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
    if "EMA_26" not in df.columns:
        df["EMA_26"] = df["Close"].ewm(span=26, adjust=False).mean()

    prev_ema12 = df["EMA_12"].shift(1)
    prev_ema26 = df["EMA_26"].shift(1)

    bullish_cross = (prev_ema12 <= prev_ema26) & (df["EMA_12"] > df["EMA_26"])
    bearish_cross = (prev_ema12 >= prev_ema26) & (df["EMA_12"] < df["EMA_26"])

    conditions = [bullish_cross, bearish_cross]
    choices    = ["BUY", "SELL"]
    df["EMA_signal"] = np.select(conditions, choices, default="HOLD")
    return df


# ---------------------------------------------------------------------------
# Strategy dispatcher
# ---------------------------------------------------------------------------

_STRATEGY_MAP = {
    "ma":   _strategy_ma,
    "rsi":  _strategy_rsi,
    "macd": _strategy_macd,
    "bb":   _strategy_bb,
    "ema":  _strategy_ema,
}

_SIGNAL_COLUMNS = {
    "ma":   "MA_signal",
    "rsi":  "RSI_signal",
    "macd": "MACD_signal_trade",
    "bb":   "BB_signal",
    "ema":  "EMA_signal",
}


def run_strategies(df: pd.DataFrame, selected_strategies: list) -> pd.DataFrame:
    """
    Run one or more trading strategies and append signal columns to the DataFrame.

    Args:
        df:                   DataFrame produced by calculate_indicators().
        selected_strategies:  List of strategy keys to run.
                              Valid keys: "ma", "rsi", "macd", "bb", "ema"
                              Pass ["all"] or omit filter to run every strategy.

    Returns:
        Updated DataFrame with signal columns appended.
    """
    result = df.copy()

    # Normalise keys to lowercase; support "all" shorthand
    keys = [k.lower().strip() for k in selected_strategies]
    if "all" in keys:
        keys = list(_STRATEGY_MAP.keys())

    print(f"\nRunning strategies: {keys}")

    for key in keys:
        if key not in _STRATEGY_MAP:
            print(f"  [WARNING] Unknown strategy '{key}' — skipping.")
            continue
        info = strategies_info[key]
        print(f"  → {info['name']} ...")
        result = _STRATEGY_MAP[key](result)
        col = _SIGNAL_COLUMNS[key]
        counts = result[col].value_counts().to_dict()
        print(f"     Signals  |  BUY: {counts.get('BUY', 0)}  "
              f"SELL: {counts.get('SELL', 0)}  "
              f"HOLD: {counts.get('HOLD', 0)}")

    print("All selected strategies executed successfully.\n")
    return result


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Resolve sibling package paths when running as a script
    project_root = os.path.join(os.path.dirname(__file__), "..")
    sys.path.append(os.path.join(project_root, "data"))
    sys.path.append(os.path.join(project_root, "indicators"))

    from data_fetcher import fetch_stock_data
    from indicators import calculate_indicators

    # 1. Fetch data
    raw_df = fetch_stock_data("AAPL", "1d", "6mo")

    # 2. Calculate indicators
    df_with_indicators = calculate_indicators(raw_df)

    # 3. Run ALL strategies
    all_keys = list(_STRATEGY_MAP.keys())   # ["ma", "rsi", "macd", "bb", "ema"]
    final_df = run_strategies(df_with_indicators, all_keys)

    # 4. Print results
    signal_cols = list(_SIGNAL_COLUMNS.values())

    print("--- DataFrame shape ---")
    print(final_df.shape)

    print("\n--- All columns ---")
    print(final_df.columns.tolist())

    print("\n--- Last 10 rows (signal columns only) ---")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print(final_df[["Date", "Close"] + signal_cols].tail(10).to_string(index=False))

    print("\n--- Strategy info registry ---")
    for key, info in strategies_info.items():
        print(f"\n[{key.upper()}] {info['name']}")
        print(f"  Description : {info['description']}")
        print(f"  Rules       : {info['rules']}")