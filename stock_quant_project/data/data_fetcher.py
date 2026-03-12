import yfinance as yf
import pandas as pd


def fetch_stock_data(symbol: str, interval: str, period: str) -> pd.DataFrame:
    """
    Fetch stock data from Yahoo Finance.

    Args:
        symbol:   Ticker symbol, e.g. "AAPL"
        interval: Data interval, e.g. "1d", "1h", "5m"
        period:   Lookback period, e.g. "6mo", "1y", "5d"

    Returns:
        pandas DataFrame with columns: Date, Open, High, Low, Close, Volume
    """
    print(f"[data_fetcher] Fetching {symbol} | interval={interval} | period={period} ...")

    ticker = yf.Ticker(symbol)
    df = ticker.history(interval=interval, period=period)

    if df.empty:
        print(f"[data_fetcher] WARNING: No data returned for '{symbol}'. "
              "Check the symbol, interval, and period values.")
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])

    # Keep only the required columns (history() may include Dividends, Stock Splits, etc.)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()

    # Move the index (DatetimeIndex) into a plain column called "Date"
    df.reset_index(inplace=True)
    df.rename(columns={"index": "Date", "Datetime": "Date"}, inplace=True)

    # Ensure the Date column is named consistently regardless of interval
    if "Date" not in df.columns and df.columns[0] != "Date":
        df.rename(columns={df.columns[0]: "Date"}, inplace=True)

    # Reorder columns explicitly
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    print(f"[data_fetcher] Successfully fetched {len(df)} rows for {symbol}.")
    return df


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    data = fetch_stock_data("AAPL", "1d", "6mo")
    print("\n--- First 5 rows ---")
    print(data.head())
    print("\n--- DataFrame info ---")
    print(data.info())