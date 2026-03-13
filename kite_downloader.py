"""
kite_option_downloader.py
--------------------------------
Download REAL NIFTY options OHLC using Zerodha Kite Connect
and save to data/NIFTY50.csv in a format usable by your backtester.

Requires:
    pip install kiteconnect pandas

Usage:
    1) First generate ACCESS_TOKEN using generate_token.py
    2) Paste API_KEY and ACCESS_TOKEN below
    3) Run: python kite_option_downloader.py
"""

import os
import datetime as dt
import pandas as pd
from kiteconnect import KiteConnect

# ==========================
# CONFIG – FILL THESE
# ==========================
API_KEY      = "45y3p3quci9j043t"
ACCESS_TOKEN = "8ViN90N6FIr1DKwLeT5WfL6ZHN0Ss55d"   # from generate_token.py

# Index token for NIFTY 50 spot
NIFTY_INDEX_TOKEN = 256265

OUTPUT_DIR  = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "NIFTY50.csv")

# How many days of history to fetch (keep it small at first)
DAYS_BACK = 90     # you can later try 180, 365, etc.

# How wide a strike range around spot (to limit data size)
STRIKE_RANGE = 500   # +/- 500 points around min/max spot in your range


def get_kite():
    kite = KiteConnect(api_key=API_KEY)
    kite.set_access_token(ACCESS_TOKEN)
    return kite


def download_nifty_index_5m(kite, start_date, end_date):
    """
    Download 5-minute candles for NIFTY index.
    Returns DataFrame with DateTime, Date, Close (spot).
    """
    from_dt = dt.datetime.combine(start_date, dt.time(9, 15))
    to_dt   = dt.datetime.combine(end_date, dt.time(15, 30))

    print(f"📊 Downloading NIFTY index 5m from {from_dt.date()} to {to_dt.date()} ...")
    data = kite.historical_data(
        instrument_token=NIFTY_INDEX_TOKEN,
        from_date=from_dt,
        to_date=to_dt,
        interval="5minute",
        continuous=False,
        oi=False
    )

    if not data:
        raise RuntimeError("No index data returned. Check permissions / token.")

    df = pd.DataFrame(data)
    df["DateTime"] = pd.to_datetime(df["date"])
    df["Date"] = df["DateTime"].dt.date
    df.rename(columns={"close": "SpotClose"}, inplace=True)
    df = df[["DateTime", "Date", "SpotClose"]].copy()

    # Daily "entry" spot = first candle of the day
    daily_spot = (
        df.sort_values("DateTime")
          .groupby("Date")["SpotClose"]
          .first()
          .rename("Underlying_Spot_Entry")
    )

    return df, daily_spot


def load_nfo_instruments(kite, cache_file=os.path.join(OUTPUT_DIR, "instruments_nfo.csv")):
    """
    Load NFO instruments (from cache if exists, else from Kite and save).
    """
    if os.path.exists(cache_file):
        print(f"📁 Loading cached instruments from {cache_file}")
        inst = pd.read_csv(cache_file)
        inst["expiry"] = pd.to_datetime(inst["expiry"]).dt.date
        return inst

    print("🔍 Downloading NFO instruments from Kite (once)...")
    inst_list = kite.instruments("NFO")
    inst = pd.DataFrame(inst_list)
    inst["expiry"] = pd.to_datetime(inst["expiry"]).dt.date

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inst.to_csv(cache_file, index=False)
    print(f"💾 Saved instruments to {cache_file}")
    return inst


def build_option_universe(inst, start_date, end_date, min_spot, max_spot, strike_range):
    """
    Filter NFO instruments down to NIFTY options around our spot range.
    """
    # Only NIFTY options
    nifty_opts = inst[
        (inst["name"] == "NIFTY") &
        (inst["segment"] == "NFO-OPT") &
        (inst["instrument_type"].isin(["CE", "PE"]))
    ].copy()

    # Filter by expiry within our test window (a bit extra margin)
    buffer_days = 7
    nifty_opts = nifty_opts[
        (nifty_opts["expiry"] >= start_date) &
        (nifty_opts["expiry"] <= end_date + dt.timedelta(days=buffer_days))
    ]

    # Filter by strike around our spot range
    lower_strike = max(0, min_spot - strike_range)
    upper_strike = max_spot + strike_range
    nifty_opts = nifty_opts[
        (nifty_opts["strike"] >= lower_strike) &
        (nifty_opts["strike"] <= upper_strike)
    ]

    print(f"✅ Option universe size: {len(nifty_opts)} instruments")
    return nifty_opts


def download_options_5m(kite, opt_universe, start_date, end_date, daily_spot):
    """
    For each option instrument in universe, download 5m OHLCV,
    attach Underlying_Spot_Entry by Date, and return a combined DataFrame.
    """
    from_dt = dt.datetime.combine(start_date, dt.time(9, 15))
    to_dt   = dt.datetime.combine(end_date, dt.time(15, 30))

    all_chunks = []
    total = len(opt_universe)
    print(f"📥 Downloading 5m data for {total} option instruments...")

    for i, (_, row) in enumerate(opt_universe.iterrows(), start=1):
        token = int(row["instrument_token"])
        strike = float(row["strike"])
        inst_type = row["instrument_type"]  # CE / PE
        expiry = row["expiry"]

        print(f"  [{i}/{total}] {row['tradingsymbol']} (strike={strike}, {inst_type}, exp={expiry}) ... ", end="")

        try:
            data = kite.historical_data(
                instrument_token=token,
                from_date=from_dt,
                to_date=to_dt,
                interval="5minute",
                continuous=False,
                oi=False
            )
        except Exception as e:
            print(f"❌ error: {e}")
            continue

        if not data:
            print("no data.")
            continue

        df_opt = pd.DataFrame(data)
        df_opt["DateTime"] = pd.to_datetime(df_opt["date"])
        df_opt["Date"]     = df_opt["DateTime"].dt.date

        # Merge in underlying spot entry for that Date
        df_opt = df_opt.merge(
            daily_spot.to_frame(),
            left_on="Date",
            right_index=True,
            how="left"
        )

        df_opt["Strike"]     = strike
        df_opt["OptionType"] = inst_type
        df_opt["Expiry"]     = expiry

        # Standardize column names
        df_opt.rename(columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }, inplace=True)

        # Keep only columns our backtester cares about
        df_opt = df_opt[
            ["DateTime", "Open", "High", "Low", "Close", "Volume",
             "Date", "Underlying_Spot_Entry", "Strike", "OptionType", "Expiry"]
        ]

        all_chunks.append(df_opt)
        print(f"✅ {len(df_opt)} rows")

    if not all_chunks:
        raise RuntimeError("No option data downloaded. Check permissions or filters.")

    df_all = pd.concat(all_chunks, ignore_index=True)
    df_all = df_all.sort_values("DateTime").reset_index(drop=True)
    return df_all


def main():
    kite = get_kite()

    today = dt.date.today()
    start_date = today - dt.timedelta(days=DAYS_BACK)
    end_date   = today

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1) Index data
    idx_df, daily_spot = download_nifty_index_5m(kite, start_date, end_date)
    min_spot = daily_spot.min()
    max_spot = daily_spot.max()
    print(f"🔎 Spot range in window: {min_spot:.2f} → {max_spot:.2f}")

    # 2) Instruments
    inst = load_nfo_instruments(kite)

    # 3) Option universe (NIFTY options around spot range)
    opt_universe = build_option_universe(inst, start_date, end_date, min_spot, max_spot, STRIKE_RANGE)

    # 4) Download options OHLCV
    df_opts = download_options_5m(kite, opt_universe, start_date, end_date, daily_spot)

    print(f"\n✅ Total option rows downloaded: {len(df_opts)}")
    print(f"Saving to: {OUTPUT_FILE}")
    df_opts.to_csv(OUTPUT_FILE, index=False)
    print("💾 Saved successfully!")


if __name__ == "__main__":
    main()
