import pandas as pd
from typing import Dict
from screener.config import CONSOLIDATION_LOOKBACK, CONSOLIDATION_PERCENTAGE, BREAKOUT_PERCENTAGE


def is_consolidating(df: pd.DataFrame, lookback: int = CONSOLIDATION_LOOKBACK,
                     percentage: float = CONSOLIDATION_PERCENTAGE) -> bool:
    recent = df.tail(lookback)
    if len(recent) < lookback:
        return False
    max_close = recent['Close'].max()
    min_close = recent['Close'].min()
    threshold = 1 - (percentage / 100)
    return min_close > (max_close * threshold)


def is_breaking_out(df: pd.DataFrame, percentage: float = BREAKOUT_PERCENTAGE) -> bool:
    if len(df) < CONSOLIDATION_LOOKBACK + 2:
        return False
    last_close = df['Close'].iloc[-1]
    prior = df.iloc[:-1]
    if is_consolidating(prior, percentage=percentage):
        prior_max = prior['Close'].iloc[-CONSOLIDATION_LOOKBACK:].max()
        if last_close > prior_max:
            return True
    return False


def is_breaking_down(df: pd.DataFrame, percentage: float = BREAKOUT_PERCENTAGE) -> bool:
    if len(df) < CONSOLIDATION_LOOKBACK + 2:
        return False
    last_close = df['Close'].iloc[-1]
    prior = df.iloc[:-1]
    if is_consolidating(prior, percentage=percentage):
        prior_min = prior['Close'].iloc[-CONSOLIDATION_LOOKBACK:].min()
        if last_close < prior_min:
            return True
    return False


def scan_batch(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for sym, df in data.items():
        if len(df) < CONSOLIDATION_LOOKBACK + 2:
            continue
        if is_breaking_out(df):
            status = 'Breakout Up'
        elif is_breaking_down(df):
            status = 'Breakout Down'
        elif is_consolidating(df):
            status = 'Consolidating'
        else:
            continue
        rows.append({
            'Symbol': sym,
            'Status': status,
            'Close': round(float(df['Close'].iloc[-1]), 2),
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=['Symbol', 'Status', 'Close'])
