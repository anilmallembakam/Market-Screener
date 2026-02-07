"""
Back-testing engine for the 4 trading combo strategies.

Walks through historical data, detects combo signals, and measures
forward returns after 5 / 10 / 20 days.
"""

import pandas as pd
import numpy as np
from typing import Dict, List

from screener.technical_indicators import compute_all, generate_signals
from screener.candlestick_patterns import scan_all_patterns
from screener.breakout_detector import is_breaking_out, is_breaking_down
from screener.alerts import REVERSAL_PATTERNS


# ── Signal detection ──────────────────────────────────────────────────────

def detect_combo_signal(df: pd.DataFrame, combo: str) -> bool:
    """Return True if *combo* signal is present at the end of *df*."""
    if len(df) < 50:
        return False
    try:
        enriched = compute_all(df.copy())
        signals = generate_signals(enriched)
        patterns = scan_all_patterns(df)

        rsi_signal = signals.get('RSI', '')
        macd_signal = signals.get('MACD', '')
        ema_signal = signals.get('EMA_Trend', '')
        bb_signal = signals.get('BB', '')
        adx_signal = signals.get('ADX', '')
        vol_signal = signals.get('Volume', '')

        bull_patterns = [p for p, s in patterns.items() if s == 'bullish']
        bear_patterns = [p for p, s in patterns.items() if s == 'bearish']
        has_reversal = any(p in REVERSAL_PATTERNS for p in bull_patterns)

        adx_val = enriched['ADX'].iloc[-1]
        adx_ok = pd.notna(adx_val) and adx_val > 25

        if combo == 'Trend Following':
            return (
                ('Bullish' in ema_signal) and
                adx_ok and
                ('High' in vol_signal) and
                len(bull_patterns) > 0
            )

        if combo == 'Mean Reversion':
            return (
                ('Oversold' in rsi_signal) and
                ('Lower' in bb_signal) and
                has_reversal
            )

        if combo == 'Breakout':
            return (
                is_breaking_out(df) and
                ('High' in vol_signal) and
                ('Bullish' in macd_signal)
            )

        if combo == 'Sell/Short':
            return (
                ('Overbought' in rsi_signal) and
                ('Upper' in bb_signal or len(bear_patterns) > 0)
            )

        return False
    except Exception:
        return False


# ── Single-stock back-test ────────────────────────────────────────────────

def backtest_combo(
    df: pd.DataFrame,
    symbol: str,
    combo: str,
    lookback_days: int = 252,
) -> dict:
    """Walk through *df* history and record forward returns for each signal.

    Returns a dict with win-rates, avg returns, and individual trade list.
    """
    empty = {
        'combo': combo, 'symbol': symbol, 'total_signals': 0,
        'win_rate_5d': 0.0, 'win_rate_10d': 0.0, 'win_rate_20d': 0.0,
        'avg_return_5d': 0.0, 'avg_return_10d': 0.0, 'avg_return_20d': 0.0,
        'trades': [],
    }

    if len(df) < 70:
        return empty

    end_idx = len(df) - 20          # need 20 bars of forward data
    start_idx = max(50, end_idx - lookback_days)

    trades: list = []
    skip_until = 0

    for i in range(start_idx, end_idx):
        if i < skip_until:
            continue

        window = df.iloc[:i + 1]
        if not detect_combo_signal(window, combo):
            continue

        entry_price = float(df['Close'].iloc[i])
        idx_5 = min(i + 5, len(df) - 1)
        idx_10 = min(i + 10, len(df) - 1)
        idx_20 = min(i + 20, len(df) - 1)

        ret_5 = (float(df['Close'].iloc[idx_5]) - entry_price) / entry_price * 100
        ret_10 = (float(df['Close'].iloc[idx_10]) - entry_price) / entry_price * 100
        ret_20 = (float(df['Close'].iloc[idx_20]) - entry_price) / entry_price * 100

        # Invert returns for short combo (profit from decline)
        if combo == 'Sell/Short':
            ret_5, ret_10, ret_20 = -ret_5, -ret_10, -ret_20

        entry_date = df.index[i]
        trades.append({
            'entry_date': str(entry_date.date()) if hasattr(entry_date, 'date') else str(entry_date),
            'entry_price': round(entry_price, 2),
            'return_5d': round(ret_5, 2),
            'return_10d': round(ret_10, 2),
            'return_20d': round(ret_20, 2),
        })

        skip_until = i + 5  # avoid overlapping trades

    if not trades:
        return empty

    r5 = [t['return_5d'] for t in trades]
    r10 = [t['return_10d'] for t in trades]
    r20 = [t['return_20d'] for t in trades]
    n = len(trades)

    return {
        'combo': combo,
        'symbol': symbol,
        'total_signals': n,
        'win_rate_5d': round(sum(1 for r in r5 if r > 0) / n * 100, 1),
        'win_rate_10d': round(sum(1 for r in r10 if r > 0) / n * 100, 1),
        'win_rate_20d': round(sum(1 for r in r20 if r > 0) / n * 100, 1),
        'avg_return_5d': round(float(np.mean(r5)), 2),
        'avg_return_10d': round(float(np.mean(r10)), 2),
        'avg_return_20d': round(float(np.mean(r20)), 2),
        'trades': trades,
    }


# ── Batch back-test ───────────────────────────────────────────────────────

def backtest_batch(
    data: Dict[str, pd.DataFrame],
    combo: str,
    lookback_days: int = 252,
) -> List[dict]:
    """Run *backtest_combo* across every stock in *data*."""
    results = []
    for symbol, df in data.items():
        result = backtest_combo(df, symbol, combo, lookback_days)
        if result['total_signals'] > 0:
            results.append(result)
    return results
