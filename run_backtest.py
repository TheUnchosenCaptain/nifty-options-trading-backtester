# run_backtest.py  — T315-style NIFTY options backtest runner

import pandas as pd
import matplotlib.pyplot as plt
from backtester import run_t315_backtest


def print_stats(stats: dict):
    print("\n======================================== Backtest Summary for NIFTY T315 Options ========================================")
    print(f"Initial Capital: ₹{stats['Initial Capital']:.2f}")
    print(f"Ending Capital:  ₹{stats['Ending Capital']:.2f}")
    print(f"Total Net PnL (₹): ₹{stats['Total Net PnL (₹)']:.2f}")
    print(f"Number of Trades: {stats['Number of Trades']}")
    print(f"Win Rate (%): {stats['Win Rate (%)']:.2f}")
    print(f"Average PnL per Trade (₹): ₹{stats['Average PnL per Trade (₹)']:.2f}")
    print(f"Max Drawdown (%): {stats['Max Drawdown (%)']:.2f}")
    print(f"Sharpe Ratio: {stats['Sharpe Ratio']:.6f}")
    print(f"Total Brokerage (₹): ₹{stats['Total Brokerage (₹)']:.2f}")
    print(f"Total STT (₹): ₹{stats['Total STT (₹)']:.2f}")
    print(f"Total Transaction Charges (₹): ₹{stats['Total Transaction Charges (₹)']:.2f}")
    print(f"Total SEBI Charges (₹): ₹{stats['Total SEBI Charges (₹)']:.2f}")
    print(f"Total Stamp Duty (₹): ₹{stats['Total Stamp Duty (₹)']:.2f}")
    print(f"Total GST (₹): ₹{stats['Total GST (₹)']:.2f}")
    print(f"Total Slippage (₹): ₹{stats['Total Slippage (₹)']:.2f}")
    print(f"No-trend days skipped: {stats['No-trend days skipped']}")
    print(f"No-instrument days skipped: {stats['No-instrument days skipped']}")
    print(f"No-tradable-window days skipped: {stats['No-tradable-window days skipped']}")
    print("===========================================================================================================================\n")


def plot_equity(eq_df: pd.DataFrame, trades_df: pd.DataFrame):
    if eq_df.empty:
        print("No equity data to plot.")
        return

    plt.figure(figsize=(12, 5))
    plt.plot(eq_df["Date"], eq_df["Equity"], label="Equity Curve", linewidth=2)

    # Mark SL and TP exits on equity curve (optional)
    if not trades_df.empty and "Reason" in trades_df.columns:
        sl_trades = trades_df[trades_df["Reason"] == "SL"]
        tp_trades = trades_df[trades_df["Reason"] == "TP"]

        if not sl_trades.empty:
            # map trade dates to equity values (approx by date)
            sl_eq = eq_df.set_index("Date").reindex(sl_trades["Date"])["Equity"]
            plt.scatter(sl_trades["Date"], sl_eq, marker="v", label="SL exits")

        if not tp_trades.empty:
            tp_eq = eq_df.set_index("Date").reindex(tp_trades["Date"])["Equity"]
            plt.scatter(tp_trades["Date"], tp_eq, marker="^", label="TP exits")

    plt.title("📈 NIFTY T315 Options – Equity Curve (After Costs)")
    plt.xlabel("Date")
    plt.ylabel("Equity (₹)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    print("📊 Loading NIFTY50 data (options)...")
    df = pd.read_csv("data/NIFTY50.csv")
    print(f"✅ Raw rows: {len(df)}")

    # Run the T315-style backtest (now returns 3 values)
    stats, trades_df, eq_df = run_t315_backtest(df)

    # Print stats with costs included
    print_stats(stats)

    # Show a few sample trades
    if not trades_df.empty:
        print("📋 Sample trades:")
        print(trades_df.head(10).to_string(index=False))
    else:
        print("No trades generated.")

    # Plot equity curve
    plot_equity(eq_df, trades_df)


if __name__ == "__main__":
    main()
