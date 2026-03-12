import yfinance as yf

# Fetch latest intraday data
data = yf.download("AAPL", interval="1m", period="1d")

print("\nLatest candles:\n")
print(data.tail())

print("\nLatest timestamp:\n")
print(data.index[-1])