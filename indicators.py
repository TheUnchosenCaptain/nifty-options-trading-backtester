import pandas as pd

def add_sma(df, short_window=10, long_window=50):
    df[f"SMA_{short_window}"] = df["Close"].rolling(window=short_window).mean()
    df[f"SMA_{long_window}"] = df["Close"].rolling(window=long_window).mean()
    return df
