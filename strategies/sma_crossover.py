# strategies/sma_crossover.py
# Defines when to enter/exit using simple SMA crossover
def generate_signals(df):
    # Expects df to already have 'sma_signal' and 'sma_signal_shift'
    # Entry when sma_signal goes from 0 -> 1
    df = df.copy()
    df['entry'] = ((df['sma_signal'] == 1) & (df['sma_signal_shift'] == 0)).astype(int)
    # Exit when sma_signal goes from 1 -> 0
    df['exit'] = ((df['sma_signal'] == 0) & (df['sma_signal_shift'] == 1)).astype(int)
    return df