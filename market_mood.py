import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
from typing import Dict, Tuple, Optional
from screener.alerts import score_stock
from screener.technical_indicators import compute_all
from screener.fo_data import get_expiry_dates, get_option_chain, compute_pcr
from screener.config import (
    CACHE_TTL_SECONDS, VIX_HIGH_INDIA, VIX_LOW_INDIA,
    VIX_HIGH_US, VIX_LOW_US, MOOD_WEIGHT_BULL_PCT,
    MOOD_WEIGHT_EMA_BREADTH, MOOD_WEIGHT_RSI,
)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_vix(market: str) -> Optional[float]:
    symbol = "^INDIAVIX" if market == "indian" else "^VIX"
    try:
        df = yf.download(symbol, period="5d", interval="1d",
                         auto_adjust=True, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        col = [c for c in df.columns if c.lower() == 'close']
        if col:
            return round(float(df[col[0]].dropna().iloc[-1]), 2)
        return None
    except Exception:
        return None


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _score_all_stocks(_data_keys: tuple, data: Dict[str, pd.DataFrame]) -> Dict[str, dict]:
    """Score all stocks once and cache. Used by mood, alerts, and signals."""
    results = {}
    for sym, df in data.items():
        if len(df) < 50:
            continue
        try:
            results[sym] = score_stock(df)
        except Exception:
            continue
    return results


def get_cached_scores(data: Dict[str, pd.DataFrame]) -> Dict[str, dict]:
    """Public wrapper that provides the hashable key for caching."""
    return _score_all_stocks(tuple(sorted(data.keys())), data)


def compute_breadth(data: Dict[str, pd.DataFrame]) -> dict:
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    above_ema200 = 0
    total_with_ema200 = 0
    rsi_values = []

    scores = get_cached_scores(data)

    for sym, df in data.items():
        if len(df) < 50:
            continue
        try:
            enriched = compute_all(df.copy())
            last = enriched.iloc[-1]

            rsi = last.get('RSI', np.nan)
            if pd.notna(rsi):
                rsi_values.append(float(rsi))

            ema200 = last.get('EMA_200', np.nan)
            close = float(last['Close'])
            if pd.notna(ema200):
                total_with_ema200 += 1
                if close > ema200:
                    above_ema200 += 1

            result = scores.get(sym)
            if result:
                if result['bullish_score'] > result['bearish_score']:
                    bullish_count += 1
                elif result['bearish_score'] > result['bullish_score']:
                    bearish_count += 1
                else:
                    neutral_count += 1
        except Exception:
            continue

    total_scored = bullish_count + bearish_count + neutral_count
    pct_above_ema200 = (
        round(above_ema200 / total_with_ema200 * 100, 1)
        if total_with_ema200 > 0 else 0.0
    )
    avg_rsi = round(float(np.mean(rsi_values)), 1) if rsi_values else 50.0

    bull_pct = (bullish_count / total_scored * 100) if total_scored > 0 else 50.0
    rsi_mood = max(0, min(100, (avg_rsi - 30) / 40 * 100))
    mood_score = round(
        MOOD_WEIGHT_BULL_PCT * bull_pct +
        MOOD_WEIGHT_EMA_BREADTH * pct_above_ema200 +
        MOOD_WEIGHT_RSI * rsi_mood,
        1
    )
    mood_score = max(0, min(100, mood_score))

    return {
        'bullish_count': bullish_count,
        'bearish_count': bearish_count,
        'neutral_count': neutral_count,
        'total_scored': total_scored,
        'pct_above_ema200': pct_above_ema200,
        'avg_rsi': avg_rsi,
        'mood_score': mood_score,
    }


def fetch_index_pcr(index_symbol: str) -> Optional[float]:
    options_map = {
        '^NSEI': '^NSEI',
        '^NSEBANK': '^NSEBANK',
        '^GSPC': 'SPY',
    }
    ticker = options_map.get(index_symbol, index_symbol)
    try:
        expiries, _ = get_expiry_dates(ticker)
        if not expiries:
            return None
        chain_result, _ = get_option_chain(ticker, expiries[0])
        if chain_result is None:
            return None
        calls, puts = chain_result
        pcr = compute_pcr(calls, puts)
        return pcr.get('PCR (OI)')
    except Exception:
        return None


def get_mood_label(mood_score: float) -> Tuple[str, str]:
    if mood_score < 30:
        return "Extreme Fear", "#c62828"
    elif mood_score < 45:
        return "Fear", "#ef6c00"
    elif mood_score < 55:
        return "Neutral", "#fdd835"
    elif mood_score < 70:
        return "Greed", "#66bb6a"
    else:
        return "Extreme Greed", "#2e7d32"


def generate_market_verdict(mood_score: float, vix: Optional[float],
                            market: str) -> str:
    if market == "indian":
        vix_low, vix_high = VIX_LOW_INDIA, VIX_HIGH_INDIA
    else:
        vix_low, vix_high = VIX_LOW_US, VIX_HIGH_US

    if vix is not None and vix > vix_high:
        return (f"High volatility (VIX: {vix:.1f}) -- "
                "Widen strikes or reduce position size for straddles")
    elif vix is not None and vix < vix_low and 40 <= mood_score <= 60:
        return (f"Low VIX ({vix:.1f}) + range-bound sentiment -- "
                "Good conditions for Short Straddles")
    elif mood_score > 65:
        return ("Bullish bias detected -- "
                "Consider directional CE buys or bullish spreads")
    elif mood_score < 35:
        return ("Bearish bias detected -- "
                "Consider directional PE buys or bearish spreads")
    else:
        return ("Mixed/neutral sentiment -- "
                "Range-bound day likely, Short Straddles viable with normal SL")
