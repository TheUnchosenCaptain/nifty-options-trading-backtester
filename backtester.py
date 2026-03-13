# backtester.py - T315-style NIFTY options backtest with full costs

import pandas as pd
import numpy as np
from datetime import time as dtime


# ---------------------------------------------------
# Cost model for Zerodha-style NIFTY options trading
# ---------------------------------------------------
def compute_option_costs(entry_price,
                         exit_price,
                         qty=75,
                         brokerage_per_order=20.0,
                         txn_rate=0.0003503,   # 0.03503%
                         stt_rate=0.001,       # 0.1% on sell premium
                         sebi_per_crore=10.0,  # ₹10 per 1 crore turnover
                         stamp_rate=0.00003,   # 0.003% on buy premium
                         gst_rate=0.18,
                         slippage_points=0.5):
    """
    Returns:
        total_cost      -> all charges + slippage
        cost_breakdown  -> dict of individual components
    """

    premium_buy = entry_price * qty
    premium_sell = exit_price * qty
    turnover = premium_buy + premium_sell

    # Brokerage: 2 orders (buy + sell)
    brokerage = 2 * brokerage_per_order

    # STT on sell premium only
    stt = stt_rate * premium_sell

    # Transaction charges on total premium
    txn_charges = txn_rate * turnover

    # SEBI charges: ₹10 per crore of turnover
    sebi_charges = (turnover / 10_000_000.0) * sebi_per_crore

    # Stamp duty on buy premium only
    stamp = stamp_rate * premium_buy

    # GST on (brokerage + txn + sebi)
    gst = gst_rate * (brokerage + txn_charges + sebi_charges)

    # Slippage: assume slippage_points worse on entry AND exit
    slippage_cost = slippage_points * qty * 2.0

    total_cost = brokerage + stt + txn_charges + sebi_charges + stamp + gst + slippage_cost

    breakdown = {
        "brokerage": brokerage,
        "stt": stt,
        "txn": txn_charges,
        "sebi": sebi_charges,
        "stamp": stamp,
        "gst": gst,
        "slippage": slippage_cost,
    }
    return total_cost, breakdown


# ---------------------------------------------------
# Core T315-style backtest
# ---------------------------------------------------
def run_t315_backtest(
    df,
    initial_capital=50_000.0,
    lot_size=75,
    fast_ema=5,
    slow_ema=20,
    min_trend_diff=10,      # points gap between fast & slow EMA to call it a trend
    entry_time=dtime(9, 25),
    exit_time=dtime(15, 15),
    sl_points=25.5,
    tp_points=59.5,
    slippage_points=0.5,
):
    """
    T315-style NIFTY options strategy:

    - Uses underlying spot from 'Underlying_Spot_Entry' column to compute EMAs.
    - For each trading day:
        * Compute fast/slow EMAs on spot.
        * At `entry_time` decide direction:
            - fast > slow + min_trend_diff -> BUY CE (UP day)
            - fast < slow - min_trend_diff -> BUY PE (DOWN day)
            - otherwise: skip day.
        * Select the option (CE/PE) whose Strike is closest to spot at entry.
        * Enter at first candle >= entry_time for that symbol.
        * Exit intraday:
            - SL: entry_price - sl_points
            - TP: entry_price + tp_points
            - Or last candle before `exit_time` (EOD) if neither hit.
    - Always trades 1 lot (qty = lot_size).
    - Applies realistic costs via compute_option_costs().

    Returns:
        stats      -> dict
        trades_df  -> DataFrame of individual trades
        equity_df  -> DataFrame [Date, Equity]
    """

    df = df.copy()

    # ---- Normalise datetimes ----
    if "DateTime" not in df.columns:
        raise KeyError("DataFrame must have 'DateTime' column")

    df["DateTime"] = pd.to_datetime(df["DateTime"])
    df = df.sort_values("DateTime").reset_index(drop=True)

    # Date column (pure date) for grouping
    if "Date" in df.columns:
        df["TradeDate"] = pd.to_datetime(df["Date"]).dt.date
    else:
        df["TradeDate"] = df["DateTime"].dt.date

    # Underlying spot series per row
    if "Underlying_Spot_Entry" not in df.columns:
        raise KeyError("DataFrame must contain 'Underlying_Spot_Entry' column for spot values.")

    # Numeric conversions
    for col in ["Open", "High", "Low", "Close", "Underlying_Spot_Entry", "Strike"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Close", "Underlying_Spot_Entry"]).reset_index(drop=True)

    capital = float(initial_capital)
    equity_points = []   # (date, equity)
    trades = []

    total_brokerage = 0.0
    total_stt = 0.0
    total_txn = 0.0
    total_sebi = 0.0
    total_stamp = 0.0
    total_gst = 0.0
    total_slippage = 0.0

    # ---- Loop day by day ----
    grouped = df.groupby("TradeDate", sort=True)

    no_trend_days = 0
    no_instr_days = 0
    no_window_days = 0

    for trade_date, day_df in grouped:
        day_df = day_df.sort_values("DateTime").reset_index(drop=True)

        # Restrict to market hours window
        mask_window = day_df["DateTime"].dt.time.between(entry_time, exit_time)
        if not mask_window.any():
            no_window_days += 1
            equity_points.append((trade_date, capital))
            continue

        # Build spot series for the day
        spot_series = (
            day_df[["DateTime", "Underlying_Spot_Entry"]]
            .drop_duplicates(subset=["DateTime"])
            .set_index("DateTime")["Underlying_Spot_Entry"]
        )

        # EMAs on spot
        fast = spot_series.ewm(span=fast_ema, adjust=False).mean()
        slow = spot_series.ewm(span=slow_ema, adjust=False).mean()

        # Choose reference time ~ entry_time
        entry_rows = day_df[day_df["DateTime"].dt.time >= entry_time]
        if entry_rows.empty:
            no_window_days += 1
            equity_points.append((trade_date, capital))
            continue

        entry_ref_time = entry_rows["DateTime"].iloc[0]

        # Get latest EMA values up to entry_ref_time
        try:
            fast_val = fast.loc[:entry_ref_time].iloc[-1]
            slow_val = slow.loc[:entry_ref_time].iloc[-1]
            spot_at_entry = spot_series.loc[:entry_ref_time].iloc[-1]
        except IndexError:
            no_spot = True
            no_window_days += 1
            equity_points.append((trade_date, capital))
            continue

        # Trend decision
        diff = fast_val - slow_val
        if diff > min_trend_diff:
            direction = "UP"
            opt_type = "CE"
        elif diff < -min_trend_diff:
            direction = "DOWN"
            opt_type = "PE"
        else:
            no_trend_days += 1
            equity_points.append((trade_date, capital))
            continue

        # Pick nearest strike for that option type around entry time
        side_df = day_df[
            (day_df["OptionType"].str.upper() == opt_type)
            & (day_df["DateTime"].dt.time >= entry_time)
            & (day_df["DateTime"].dt.time <= exit_time)
        ]

        if side_df.empty:
            no_instr_days += 1
            equity_points.append((trade_date, capital))
            continue

        # We only look at candles at the first entry_ref_time for fairness
        side_at_entry = side_df[side_df["DateTime"] == entry_ref_time]
        if side_at_entry.empty:
            # If nothing exactly at ref time, allow within first 10 mins
            tmp = side_df[side_df["DateTime"] <= (entry_ref_time + pd.Timedelta(minutes=10))]
            if tmp.empty:
                no_instr_days += 1
                equity_points.append((trade_date, capital))
                continue
            first_time = tmp["DateTime"].min()
            side_at_entry = tmp[tmp["DateTime"] == first_time]

        # Choose strike closest to spot, then nearest expiry
        side_at_entry = side_at_entry.copy()
        side_at_entry["StrikeDiff"] = (side_at_entry["Strike"] - spot_at_entry).abs()
        chosen = side_at_entry.sort_values(["StrikeDiff", "Expiry"]).iloc[0]

        chosen_strike = float(chosen["Strike"])
        chosen_expiry = chosen["Expiry"]

        # All candles for this chosen instrument on this day
        instr_df = day_df[
            (day_df["OptionType"].str.upper() == opt_type)
            & (day_df["Strike"] == chosen_strike)
            & (day_df["Expiry"] == chosen_expiry)
        ].sort_values("DateTime").reset_index(drop=True)

        instr_df = instr_df[instr_df["DateTime"].dt.time.between(entry_time, exit_time)]
        if instr_df.empty:
            no_instr_days += 1
            equity_points.append((trade_date, capital))
            continue

        # ENTRY at first candle in instr_df
        entry_row = instr_df.iloc[0]
        entry_time_actual = entry_row["DateTime"]
        entry_price_raw = float(entry_row["Close"])

        # Apply slippage (worse price on entry)
        entry_price = entry_price_raw + slippage_points
        qty = lot_size

        # SL & TP levels
        sl_level = entry_price - sl_points
        tp_level = entry_price + tp_points

        exit_price = entry_price  # will update
        exit_reason = "EOD"

        # Walk through remaining candles to exit
        for j in range(1, len(instr_df)):
            row_j = instr_df.iloc[j]
            high = float(row_j["High"])
            low = float(row_j["Low"])

            # Check SL first (risk first), then TP
            hit_sl = low <= sl_level
            hit_tp = high >= tp_level

            if hit_sl:
                exit_price_raw = sl_level
                exit_reason = "SL"
                break
            if hit_tp:
                exit_price_raw = tp_level
                exit_reason = "TP"
                break
        else:
            # No SL/TP hit -> exit at last close (EOD)
            exit_price_raw = float(instr_df.iloc[-1]["Close"])
            exit_reason = "EOD"

        # Apply slippage on exit (worse price when SELLing long option)
        exit_price = max(exit_price_raw - slippage_points, 0.05)  # avoid negative/zero

        # Gross PnL in rupees
        gross_points = exit_price - entry_price
        gross_pnl = gross_points * qty

        # Costs
        total_cost, cb = compute_option_costs(
            entry_price,
            exit_price,
            qty=qty,
            slippage_points=slippage_points
        )

        net_pnl = gross_pnl - total_cost
        capital += net_pnl

        total_brokerage += cb["brokerage"]
        total_stt += cb["stt"]
        total_txn += cb["txn"]
        total_sebi += cb["sebi"]
        total_stamp += cb["stamp"]
        total_gst += cb["gst"]
        total_slippage += cb["slippage"]

        equity_points.append((trade_date, capital))

        trades.append({
            "Date": trade_date,
            "Direction": direction,
            "Strike": chosen_strike,
            "Expiry": chosen_expiry,
            "EntryTime": entry_time_actual,
            "EntryPrice": round(entry_price, 2),
            "ExitPrice": round(exit_price, 2),
            "Points": round(gross_points, 2),
            "GrossPnL": round(gross_pnl, 2),
            "NetPnL": round(net_pnl, 2),
            "Reason": exit_reason,
        })

    # ---------- Build outputs ----------
    trades_df = pd.DataFrame(trades)

    # Equity series as DataFrame
    if equity_points:
        eq_df = pd.DataFrame(equity_points, columns=["Date", "Equity"])
        eq_df.sort_values("Date", inplace=True)
    else:
        eq_df = pd.DataFrame(columns=["Date", "Equity"])

    total_net_pnl = capital - initial_capital
    num_trades = len(trades_df)
    win_rate = (trades_df["NetPnL"] > 0).mean() * 100 if num_trades > 0 else 0.0
    avg_pnl = trades_df["NetPnL"].mean() if num_trades > 0 else 0.0

    # Drawdown / Sharpe on daily equity
    if len(eq_df) > 1:
        eq_series = eq_df["Equity"].astype(float)
        cummax = eq_series.cummax()
        drawdown = (cummax - eq_series) / cummax
        max_dd = float(drawdown.max() * 100)

        returns = eq_series.pct_change().dropna()
        sharpe = float(
            (returns.mean() / returns.std() * np.sqrt(252))
        ) if returns.std() != 0 else 0.0
    else:
        max_dd = 0.0
        sharpe = 0.0

    stats = {
        "Initial Capital": float(initial_capital),
        "Ending Capital": float(capital),
        "Total Net PnL (₹)": float(total_net_pnl),
        "Number of Trades": int(num_trades),
        "Win Rate (%)": float(win_rate),
        "Average PnL per Trade (₹)": float(avg_pnl),
        "Max Drawdown (%)": float(max_dd),
        "Sharpe Ratio": float(sharpe),
        "Total Brokerage (₹)": float(total_brokerage),
        "Total STT (₹)": float(total_stt),
        "Total Transaction Charges (₹)": float(total_txn),
        "Total SEBI Charges (₹)": float(total_sebi),
        "Total Stamp Duty (₹)": float(total_stamp),
        "Total GST (₹)": float(total_gst),
        "Total Slippage (₹)": float(total_slippage),
        "No-trend days skipped": int(no_trend_days),
        "No-instrument days skipped": int(no_instr_days),
        "No-tradable-window days skipped": int(no_window_days),
    }

    return stats, trades_df, eq_df
