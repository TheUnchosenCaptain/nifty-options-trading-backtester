import pandas as pd
import os

def fetch_nifty50_data(file_path="data/NIFTY50.csv"):
    """
    Loads and cleans NIFTY50 data from CSV for backtesting.
    Ensures 'Date' is datetime and all price columns are numeric.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} not found. Please run download_data.py first.")

    df = pd.read_csv(file_path)

    # Normalize column names
    df.columns = [c.strip().title().replace(' ', '') for c in df.columns]

    # Ensure 'Date' column exists and is datetime
    if 'Date' not in df.columns:
        raise ValueError("CSV must contain a 'Date' column.")
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').set_index('Date')

    # Convert numeric columns safely
    for col in ['Open', 'High', 'Low', 'Close', 'Adjclose', 'Volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop rows with missing Close prices
    df.dropna(subset=['Close'], inplace=True)

    return df
