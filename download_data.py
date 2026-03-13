import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os

def fetch_and_save(symbol="^NSEI", name="NIFTY50", days=59):
    """Fetch last `days` of 5-minute data for given symbol."""
    end = datetime.now()
    start = end - timedelta(days=days)

    print(f"📊 Downloading 5-minute data for {symbol} ({start.date()} → {end.date()}) ...")

    try:
        df = yf.download(
            symbol,
            start=start,
            end=end,
            interval="5m",
            progress=False,
            auto_adjust=False
        )

        if df.empty:
            raise ValueError("No data returned (possible weekend or Yahoo limitation).")

        # Reset index to keep Datetime column
        df = df.reset_index()

        # Rename columns to standard form
        df.rename(
            columns={
                "Datetime": "DateTime",
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Adj Close": "Adj Close",
                "Volume": "Volume"
            },
            inplace=True
        )

        # Ensure all key columns exist
        required_cols = ["DateTime", "Open", "High", "Low", "Close"]
        for col in required_cols:
            if col not in df.columns:
                raise KeyError(f"Missing column: {col}")

        os.makedirs("data", exist_ok=True)
        df.to_csv(f"data/{name}.csv", index=False)
        print(f"✅ Saved → data/{name}.csv ({len(df)} rows)")

    except Exception as e:
        print(f"❌ Error fetching {name}: {e}")

if __name__ == "__main__":
    fetch_and_save()
