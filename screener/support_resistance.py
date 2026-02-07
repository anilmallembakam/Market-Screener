import numpy as np
import pandas as pd
from typing import List, Tuple
from screener.config import SR_PIVOT_WINDOW, SR_CLUSTER_TOLERANCE_PCT


def find_pivot_highs(df: pd.DataFrame, window: int = SR_PIVOT_WINDOW) -> pd.Series:
    highs = df['High']
    pivots = highs == highs.rolling(window=2 * window + 1, center=True).max()
    return pivots


def find_pivot_lows(df: pd.DataFrame, window: int = SR_PIVOT_WINDOW) -> pd.Series:
    lows = df['Low']
    pivots = lows == lows.rolling(window=2 * window + 1, center=True).min()
    return pivots


def cluster_levels(prices: np.ndarray,
                   tolerance_pct: float = SR_CLUSTER_TOLERANCE_PCT) -> List[float]:
    if len(prices) == 0:
        return []
    sorted_prices = np.sort(prices)
    clusters = []
    current_cluster = [sorted_prices[0]]
    for price in sorted_prices[1:]:
        if current_cluster[0] > 0 and (price - current_cluster[0]) / current_cluster[0] * 100 <= tolerance_pct:
            current_cluster.append(price)
        else:
            clusters.append(round(float(np.mean(current_cluster)), 2))
            current_cluster = [price]
    clusters.append(round(float(np.mean(current_cluster)), 2))
    return clusters


def calculate_classic_pivots(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    h, l, c = float(last['High']), float(last['Low']), float(last['Close'])
    pp = (h + l + c) / 3
    return {
        'PP': round(pp, 2),
        'R1': round(2 * pp - l, 2),
        'R2': round(pp + (h - l), 2),
        'R3': round(h + 2 * (pp - l), 2),
        'S1': round(2 * pp - h, 2),
        'S2': round(pp - (h - l), 2),
        'S3': round(l - 2 * (h - pp), 2),
    }


def detect_levels(df: pd.DataFrame, window: int = SR_PIVOT_WINDOW,
                  tolerance_pct: float = SR_CLUSTER_TOLERANCE_PCT
                  ) -> Tuple[List[float], List[float], dict]:
    pivot_highs = df.loc[find_pivot_highs(df, window), 'High'].values
    pivot_lows = df.loc[find_pivot_lows(df, window), 'Low'].values

    resistance = cluster_levels(pivot_highs, tolerance_pct)
    support = cluster_levels(pivot_lows, tolerance_pct)
    pivots = calculate_classic_pivots(df)

    return resistance, support, pivots
