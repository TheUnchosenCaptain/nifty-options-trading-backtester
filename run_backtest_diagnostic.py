# run_backtest_diagnostic.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from backtester import run_sma_backtest

def print_df_info(df):
    print("=== Data summary ===")
    print("Rows:", len(df))
    print("Columns:", df.columns.tolist())
    # date range
    if "DateTime" in df.columns:
        print("DateTime range:", df["DateTime"].min(), "->", df["DateTime"].max())
    elif "Date" in df.columns:
        print("Date range:", df["Date"].min(), "->", df["Date"].max())
    print(df.head(3).to_string(index=False))
    print(df.tail(3).to_string(index=False))
    print("====================\n")

def count_signals_for_pair(df, short, long):
    tmp = df.copy()
    tmp["Close"] = pd.to_numeric(tmp["Close"], errors="coerce")
    tmp = tmp.dropna(subset=["Close"]).reset_index(drop=True)
    tmp[f"SMA_{short}"] = tmp["Close"].rolling(window=short).mean()
    tmp[f"SMA_{long}"] = tmp["Close"].rolling(window=long).mean()
    tmp["Signal"] = 0
    tmp.loc[tmp[f"SMA_{short}"] > tmp[f"SMA_{long}"], "Signal"] = 1
    tmp.loc[tmp[f"SMA_{short}"] < tmp[f"SMA_{long}"], "Signal"] = -1
    # count signal changes (entries)
    entries = ((tmp["Signal"].shift(1) <= 0) & (tmp["Signal"] == 1)).sum()
    exits = ((tmp["Signal"].shift(1) >= 0) & (tmp["Signal"] == -1)).sum()
    return int(entries), int(exits)

def main():
    print("📊 Loading NIFTY50 data...")
    df = pd.read_csv("data/NIFTY50.csv")

    # normalize common timestamp names
    dt_col = None
    for c in ["DateTime","Datetime","date","Date","Timestamp","timestamp"]:
        if c in df.columns:
            dt_col = c
            break
    if dt_col is None:
        # try index as datetime
        if df.index.name and "Unnamed" not in str(df.index.name):
            df.reset_index(inplace=True)
            dt_col = df.columns[0]
        else:
            raise KeyError("CSV must have a datetime-like column. Found: " + str(list(df.columns)))
    df["DateTime"] = pd.to_datetime(df[dt_col], errors="coerce")
    df.dropna(subset=["DateTime"], inplace=True)
    df.sort_values("DateTime", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # try to normalize Close column variants
    cols_lower = [c.lower() for c in df.columns]
    if "close" not in cols_lower:
        if "adj close" in cols_lower:
            df.rename(columns={df.columns[cols_lower.index("adj close")]: "Close"}, inplace=True)
        else:
            # try to find any column that looks like price
            cand = None
            for name in ["close","last","price","close*"]:
                if name in cols_lower:
                    cand = df.columns[cols_lower.index(name)]
                    break
            if cand:
                df.rename(columns={cand: "Close"}, inplace=True)

    # print basic info
    print_df_info(df)

    # quick check: rows count and close nulls
    print("Close column exists?", "Close" in df.columns)
    if "Close" in df.columns:
        print("Close - nulls:", df["Close"].isna().sum(), "non-nulls:", df["Close"].notna().sum())
    else:
        print("❌ No Close column found. Can't run backtest.")
        return

    # Check a few SMA pairs to see how many entry signals they'd generate
    print("\n⚙️ Signal counts for sample SMA pairs (entries, exits):")
    sample_pairs = [(5,15),(7,20),(10,30),(3,10)]
    for s,l in sample_pairs:
        entries, exits = count_signals_for_pair(df, s, l)
        print(f"  SMA({s},{l}): entries={entries}, exits={exits}")

    # Now run the uploaded backtester optimization (same loop as before)
    print("\nRunning full optimization (shows best combo) ...")
    best_pnl = -np.inf
    best_short,best_long = 0,0
    # smaller ranges first to be safe on 60-day data
    for short in range(3, 16, 2):
        for long in range(short+5, 40, 5):
            pnl, trades, win_rate = run_sma_backtest(df, short, long)
            if pnl > best_pnl:
                best_pnl = pnl
                best_short, best_long = short, long

    print(f"\n✅ Best SMA: short={best_short}, long={best_long} → PnL=₹{best_pnl:,.2f}")

    # Run final and print summary (same as old)
    pnl, trades, win_rate = run_sma_backtest(df, best_short, best_long)
    initial_capital = 100000
    ending_capital = initial_capital + pnl
    avg_pnl_per_trade = pnl / trades if trades > 0 else 0
    print("\n======================================== Backtest Summary for NIFTY50 ========================================")
    print(f"Initial Capital: ₹{initial_capital:,.2f}")
    print(f"Ending Capital:  ₹{ending_capital:,.2f}")
    print(f"Total PnL:       ₹{pnl:,.2f}")
    print(f"Number of Trades: {trades}")
    print(f"Average PnL per Trade: ₹{avg_pnl_per_trade:,.2f}")
    print(f"Win Rate (%): {win_rate:.2f}%")
    print("===============================================================================================================\n")

if __name__ == "__main__":
    main()
