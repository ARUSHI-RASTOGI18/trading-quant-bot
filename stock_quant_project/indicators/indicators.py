import pandas as pd
import sys
import os


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate technical indicators and append them as new columns.

    Indicators added:
        SMA_20        - 20-period Simple Moving Average
        EMA_20        - 20-period Exponential Moving Average
        RSI_14        - 14-period Relative Strength Index
        MACD          - MACD line  (EMA_12 - EMA_26)
        MACD_signal   - 9-period EMA of MACD line
        MACD_hist     - MACD histogram (MACD - MACD_signal)
        BB_upper      - Bollinger Band upper  (SMA_20 + 2σ)
        BB_lower      - Bollinger Band lower  (SMA_20 - 2σ)

    Args:
        df: DataFrame returned by fetch_stock_data()
            Must contain a 'Close' column.

    Returns:
        Copy of df with indicator columns appended.
    """
    print("Calculating indicators...")

    result = df.copy()
    close = result["Close"]

    # ------------------------------------------------------------------
    # 1. SMA_20 — Simple Moving Average (20 periods)
    # ------------------------------------------------------------------
    result["SMA_20"] = close.rolling(window=20).mean()

    # ------------------------------------------------------------------
    # 2. EMA_20 — Exponential Moving Average (20 periods)
    # ------------------------------------------------------------------
    result["EMA_20"] = close.ewm(span=20, adjust=False).mean()

    # ------------------------------------------------------------------
    # 3. RSI_14 — Relative Strength Index (14 periods)
    #    Formula:
    #      delta  = daily price change
    #      gain   = average of positive deltas over 14 periods
    #      loss   = average of absolute negative deltas over 14 periods
    #      RS     = gain / loss
    #      RSI    = 100 - (100 / (1 + RS))
    # ------------------------------------------------------------------
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=13, adjust=False).mean()   # Wilder smoothing ≡ span=14
    avg_loss = loss.ewm(com=13, adjust=False).mean()

    rs = avg_gain / avg_loss
    result["RSI_14"] = 100 - (100 / (1 + rs))

    # ------------------------------------------------------------------
    # 4. MACD, MACD_signal, MACD_hist
    #    MACD        = EMA_12 - EMA_26
    #    MACD_signal = 9-period EMA of MACD
    #    MACD_hist   = MACD - MACD_signal
    # ------------------------------------------------------------------
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()

    result["MACD"]        = ema_12 - ema_26
    result["MACD_signal"] = result["MACD"].ewm(span=9, adjust=False).mean()
    result["MACD_hist"]   = result["MACD"] - result["MACD_signal"]

    # ------------------------------------------------------------------
    # 5. Bollinger Bands (20 period, 2 standard deviations)
    #    BB_upper = SMA_20 + 2 * rolling_std_20
    #    BB_lower = SMA_20 - 2 * rolling_std_20
    # ------------------------------------------------------------------
    rolling_std = close.rolling(window=20).std()
    result["BB_upper"] = result["SMA_20"] + (2 * rolling_std)
    result["BB_lower"] = result["SMA_20"] - (2 * rolling_std)

    print("Indicators calculated successfully.")
    return result


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Allow running from the indicators/ directory or the project root
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
    from data_fetcher import fetch_stock_data

    # 1. Fetch data
    raw_df = fetch_stock_data("AAPL", "1d", "6mo")

    # 2. Calculate indicators
    result_df = calculate_indicators(raw_df)

    # 3. Print diagnostics
    print("\n--- DataFrame shape ---")
    print(result_df.shape)

    print("\n--- Columns ---")
    print(result_df.columns.tolist())

    print("\n--- First 5 rows ---")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print(result_df.head())