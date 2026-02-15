import pandas as pd
import numpy as np
from typing import Dict, Optional
from screener.candlestick_patterns import scan_all_patterns
from screener.technical_indicators import compute_all, generate_signals
from screener.breakout_detector import is_breaking_out, is_breaking_down


# ── Relative Strength ────────────────────────────────────────────────────

RS_LOOKBACK = 21  # ~1 month of trading days


def _pct_return(df: pd.DataFrame, lookback: int = RS_LOOKBACK) -> Optional[float]:
    """Compute percentage return over the last *lookback* bars."""
    if df is None or len(df) < lookback + 1:
        return None
    close = df['Close'].values.astype(float)
    old = close[-(lookback + 1)]
    new = close[-1]
    if old <= 0 or np.isnan(old) or np.isnan(new):
        return None
    return ((new - old) / old) * 100


def compute_relative_strength(
    data: Dict[str, pd.DataFrame],
    index_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Optional[float]]:
    """Return {symbol: RS%} where RS% = stock_return - index_return.

    Positive RS% means the stock is outperforming the index.
    If index_df is None, returns raw stock returns instead.
    """
    index_ret = _pct_return(index_df) if index_df is not None else 0.0

    rs_map: Dict[str, Optional[float]] = {}
    for sym, df in data.items():
        stock_ret = _pct_return(df)
        if stock_ret is None or index_ret is None:
            rs_map[sym] = None
        else:
            rs_map[sym] = round(stock_ret - index_ret, 1)
    return rs_map


def score_stock(df: pd.DataFrame) -> dict:
    criteria = []
    bullish = 0
    bearish = 0

    enriched = compute_all(df.copy())
    signals = generate_signals(enriched)

    # RSI
    rsi = enriched['RSI'].iloc[-1]
    if pd.notna(rsi):
        if rsi < 30:
            bullish += 1
            criteria.append({'criterion': 'RSI Oversold', 'signal': 'bullish', 'detail': f'{rsi:.1f}'})
        elif rsi > 70:
            bearish += 1
            criteria.append({'criterion': 'RSI Overbought', 'signal': 'bearish', 'detail': f'{rsi:.1f}'})

    # MACD
    macd_sig = signals.get('MACD', '')
    if 'Bullish' in macd_sig:
        bullish += 1
        criteria.append({'criterion': 'MACD', 'signal': 'bullish', 'detail': macd_sig})
    elif 'Bearish' in macd_sig:
        bearish += 1
        criteria.append({'criterion': 'MACD', 'signal': 'bearish', 'detail': macd_sig})

    # EMA
    ema_sig = signals.get('EMA_Trend', '')
    if 'Bullish' in ema_sig:
        bullish += 1
        criteria.append({'criterion': 'EMA Trend', 'signal': 'bullish', 'detail': ema_sig})
    elif 'Bearish' in ema_sig:
        bearish += 1
        criteria.append({'criterion': 'EMA Trend', 'signal': 'bearish', 'detail': ema_sig})

    # Bollinger Bands
    bb_sig = signals.get('BB', '')
    if 'Lower' in bb_sig:
        bullish += 1
        criteria.append({'criterion': 'Bollinger Band', 'signal': 'bullish', 'detail': bb_sig})
    elif 'Upper' in bb_sig:
        bearish += 1
        criteria.append({'criterion': 'Bollinger Band', 'signal': 'bearish', 'detail': bb_sig})

    # ADX
    adx_sig = signals.get('ADX', '')
    if 'Strong Bullish' in adx_sig:
        bullish += 1
        criteria.append({'criterion': 'ADX', 'signal': 'bullish', 'detail': adx_sig})
    elif 'Strong Bearish' in adx_sig:
        bearish += 1
        criteria.append({'criterion': 'ADX', 'signal': 'bearish', 'detail': adx_sig})

    # Volume
    vol_sig = signals.get('Volume', '')
    if 'High' in vol_sig:
        if bullish > bearish:
            bullish += 1
            criteria.append({'criterion': 'Volume Confirmation', 'signal': 'bullish', 'detail': vol_sig})
        elif bearish > bullish:
            bearish += 1
            criteria.append({'criterion': 'Volume Confirmation', 'signal': 'bearish', 'detail': vol_sig})

    # Breakout / Breakdown
    breakout = is_breaking_out(df)
    breakdown = is_breaking_down(df)

    if breakout:
        bullish += 2
        criteria.append({'criterion': 'Breakout', 'signal': 'bullish', 'detail': 'Breaking out of consolidation'})
    elif breakdown:
        bearish += 2
        criteria.append({'criterion': 'Breakdown', 'signal': 'bearish', 'detail': 'Breaking down from consolidation'})

    # Candlestick patterns
    patterns = scan_all_patterns(df)
    bull_patterns = [p for p, s in patterns.items() if s == 'bullish']
    bear_patterns = [p for p, s in patterns.items() if s == 'bearish']
    if bull_patterns:
        bullish += min(len(bull_patterns), 2)
        criteria.append({'criterion': 'Candlestick', 'signal': 'bullish',
                         'detail': ', '.join(bull_patterns[:3])})
    if bear_patterns:
        bearish += min(len(bear_patterns), 2)
        criteria.append({'criterion': 'Candlestick', 'signal': 'bearish',
                         'detail': ', '.join(bear_patterns[:3])})

    # Candle close quality analysis (separate filter only, does NOT affect score)
    close_info = _analyze_candle_close(df)
    close_pct = close_info['close_pct']
    body_pct = close_info['body_pct']
    is_green = close_info['is_green']

    return {
        'bullish_score': bullish,
        'bearish_score': bearish,
        'criteria': criteria,
        'patterns': patterns,
        'signals': signals,
        'is_breakout': breakout,
        'is_breakdown': breakdown,
        'close_pct': close_pct,
        'body_pct': body_pct,
        'is_green': is_green,
    }


def _analyze_candle_close(df: pd.DataFrame) -> dict:
    """Analyze the latest candle's close quality.

    Returns:
        close_pct: Where close sits in the High-Low range (0.0=low, 1.0=high)
        body_pct:  Body size as fraction of total range (0=doji, 1=marubozu)
        is_green:  True if close >= open
    """
    last = df.iloc[-1]
    o, h, l, c = float(last['Open']), float(last['High']), float(last['Low']), float(last['Close'])
    candle_range = h - l

    if candle_range <= 0:
        return {'close_pct': 0.5, 'body_pct': 0.0, 'is_green': c >= o}

    close_pct = (c - l) / candle_range          # 0.0 = closed at low, 1.0 = closed at high
    body_pct = abs(c - o) / candle_range         # body size relative to range
    is_green = c >= o

    return {'close_pct': close_pct, 'body_pct': body_pct, 'is_green': is_green}


# ── Combo Recommendation ──────────────────────────────────────────────────

REVERSAL_PATTERNS = {
    'Hammer', 'Morning Star', 'Morning Doji Star', 'Engulfing Pattern',
    'Piercing Pattern', 'Three Advancing White Soldiers', 'Inverted Hammer',
    'Abandoned Baby',
}


def recommend_combo(
    criteria: list,
    signals: dict,
    patterns: dict,
    is_breakout: bool,
    is_breakdown: bool,
) -> dict:
    """Map detected signals to the best matching trading combo (1-4).

    Returns {'combo': str, 'match_score': int, 'reason': str}.
    """
    rsi_signal = signals.get('RSI', '')
    macd_signal = signals.get('MACD', '')
    ema_signal = signals.get('EMA_Trend', '')
    bb_signal = signals.get('BB', '')
    adx_signal = signals.get('ADX', '')
    vol_signal = signals.get('Volume', '')

    bull_patterns = [p for p, s in patterns.items() if s == 'bullish']
    bear_patterns = [p for p, s in patterns.items() if s == 'bearish']
    has_reversal = any(p in REVERSAL_PATTERNS for p in bull_patterns)

    scores = {
        'Trend Following': 0,
        'Mean Reversion': 0,
        'Breakout': 0,
        'Sell/Short': 0,
    }
    reasons = {k: [] for k in scores}

    # ── Combo 1: Trend Following ──
    if 'Bullish' in ema_signal:
        scores['Trend Following'] += 1
        reasons['Trend Following'].append('EMA aligned')
    if 'Strong Bullish' in adx_signal:
        scores['Trend Following'] += 1
        reasons['Trend Following'].append('ADX strong')
    if 'High' in vol_signal:
        scores['Trend Following'] += 1
        reasons['Trend Following'].append('Volume confirms')
    if bull_patterns:
        scores['Trend Following'] += 1
        reasons['Trend Following'].append('Bullish pattern')

    # ── Combo 2: Mean Reversion ──
    if 'Oversold' in rsi_signal:
        scores['Mean Reversion'] += 1
        reasons['Mean Reversion'].append('RSI oversold')
    if 'Lower' in bb_signal:
        scores['Mean Reversion'] += 1
        reasons['Mean Reversion'].append('Near lower BB')
    if has_reversal:
        scores['Mean Reversion'] += 1
        reasons['Mean Reversion'].append('Reversal pattern')
    if 'Oversold' in rsi_signal and 'Lower' in bb_signal:
        scores['Mean Reversion'] += 1
        reasons['Mean Reversion'].append('Support zone')

    # ── Combo 3: Breakout ──
    if is_breakout:
        scores['Breakout'] += 2
        reasons['Breakout'].append('Breaking consolidation')
    if 'High' in vol_signal:
        scores['Breakout'] += 1
        reasons['Breakout'].append('High volume')
    if 'Bullish' in macd_signal:
        scores['Breakout'] += 1
        reasons['Breakout'].append('MACD bullish')
    if 'Weak' not in adx_signal and adx_signal:
        scores['Breakout'] += 1
        reasons['Breakout'].append('ADX confirming')

    # ── Combo 4: Sell / Short ──
    if 'Overbought' in rsi_signal:
        scores['Sell/Short'] += 1
        reasons['Sell/Short'].append('RSI overbought')
    if 'Upper' in bb_signal:
        scores['Sell/Short'] += 1
        reasons['Sell/Short'].append('Near upper BB')
    if bear_patterns:
        scores['Sell/Short'] += 1
        reasons['Sell/Short'].append('Bearish pattern')
    if 'Bearish' in ema_signal:
        scores['Sell/Short'] += 1
        reasons['Sell/Short'].append('EMA bearish')

    best = max(scores, key=scores.get)
    best_score = scores[best]

    if best_score < 2:
        return {'combo': 'No clear setup', 'match_score': best_score,
                'reason': 'Insufficient confluence'}

    reason_str = ' + '.join(reasons[best][:3])
    return {'combo': best, 'match_score': best_score, 'reason': reason_str}


# ── Entry Signal Detection ───────────────────────────────────────────────

from screener.config import ENTRY_EMA_PULLBACK_PCT, ENTRY_ADX_MIN, ENTRY_VOLUME_RATIO_PREFERRED

_NO_SIGNAL = {
    'has_signal': False, 'strategy': '', 'direction': '', 'strength': 'None',
    'conditions_met': [], 'conditions_missing': [],
    'entry_price': 0, 'ema20': 0, 'stop_loss': 0,
    'target_1': 0, 'target_2': 0, 'risk_pct': 0,
    'pullback_pct': 0, 'details': {},
}


def detect_entry_signal(df: pd.DataFrame, strategy: str = 'trend_following') -> list:
    """Detect if a stock currently satisfies an actionable entry setup.

    This is SEPARATE from score_stock() — it checks whether a stock
    is at a specific entry point for a given trading strategy.

    Returns a **list** of signal dicts (0, 1, or 2) so both bullish
    and bearish signals can be returned simultaneously.
    """
    if df is None or len(df) < 50:
        return []

    enriched = compute_all(df.copy())
    signals = generate_signals(enriched)

    results = []
    if strategy == 'trend_following':
        bull = _check_trend_following_entry(enriched, signals)
        if bull['has_signal']:
            results.append(bull)
        bear = _check_bearish_trend_following_entry(enriched, signals)
        if bear['has_signal']:
            results.append(bear)
    # Future: elif strategy == 'mean_reversion': ...
    return results


def _check_trend_following_entry(enriched: pd.DataFrame, signals: dict) -> dict:
    """Check Trend Following entry conditions:
    1. EMA alignment (required): close > EMA20 > EMA50 > EMA200
    2. Pullback to EMA20 (required): within 2% or Low touched EMA20
    3. Bullish candle (confirmation): green + body > 40%, or bullish pattern
    4. Volume (confirmation): ratio >= 1.5x
    5. ADX (confirmation): >= 25
    """
    last = enriched.iloc[-1]
    conditions_met = []
    conditions_missing = []

    close = float(last['Close'])
    low = float(last['Low'])
    high = float(last['High'])
    open_ = float(last['Open'])
    ema20 = float(last.get('EMA_20', np.nan))
    ema50 = float(last.get('EMA_50', np.nan))
    ema200 = float(last.get('EMA_200', np.nan))
    adx = float(last.get('ADX', np.nan))
    vol_ratio = float(last.get('Volume_Ratio', np.nan))
    atr = float(last.get('ATR', np.nan))

    # Guard against NaN
    if pd.isna(ema20) or pd.isna(ema50) or pd.isna(ema200) or ema20 <= 0:
        return {**_NO_SIGNAL, 'strategy': 'Trend Following'}

    # Condition 1: EMA alignment
    ema_aligned = close > ema20 > ema50 > ema200
    if ema_aligned:
        conditions_met.append('EMA aligned (20 > 50 > 200)')
    else:
        conditions_missing.append('EMA alignment')

    # Condition 2: Pullback to EMA20
    pullback_pct = ((close - ema20) / ema20) * 100
    ema_touched = low <= ema20 <= close  # touched intraday but closed above
    near_ema = 0 <= pullback_pct <= ENTRY_EMA_PULLBACK_PCT
    pullback_ok = near_ema or ema_touched

    if pullback_ok:
        detail = f'Pullback {pullback_pct:.1f}% from EMA20'
        if ema_touched:
            detail += ' (bounced off EMA20)'
        conditions_met.append(detail)
    else:
        conditions_missing.append(f'Pullback to EMA20 ({pullback_pct:.1f}% away)')

    # Condition 3: Bullish candle confirmation
    is_green = close >= open_
    candle_range = high - low
    body_pct = (abs(close - open_) / candle_range * 100) if candle_range > 0 else 0

    bull_patterns = []
    try:
        from screener.candlestick_patterns import scan_all_patterns
        patterns = scan_all_patterns(enriched)
        bull_patterns = [p for p, s in patterns.items() if s == 'bullish']
    except Exception:
        pass

    if is_green and body_pct > 40:
        detail = 'Bullish candle'
        if bull_patterns:
            detail += f' + {", ".join(bull_patterns[:2])}'
        conditions_met.append(detail)
    elif bull_patterns:
        conditions_met.append(f'Bullish pattern: {", ".join(bull_patterns[:2])}')
    else:
        conditions_missing.append('Bullish candle confirmation')

    # Condition 4: Volume
    if pd.notna(vol_ratio) and vol_ratio >= ENTRY_VOLUME_RATIO_PREFERRED:
        conditions_met.append(f'Volume confirmed ({vol_ratio:.1f}x avg)')
    else:
        vol_str = f'{vol_ratio:.1f}x' if pd.notna(vol_ratio) else 'N/A'
        conditions_missing.append(f'Volume ({vol_str} avg, need {ENTRY_VOLUME_RATIO_PREFERRED}x)')

    # Condition 5: ADX
    if pd.notna(adx) and adx >= ENTRY_ADX_MIN:
        conditions_met.append(f'ADX strong ({adx:.0f})')
    else:
        adx_str = f'{adx:.0f}' if pd.notna(adx) else 'N/A'
        conditions_missing.append(f'ADX >= {ENTRY_ADX_MIN} (currently {adx_str})')

    # Determine signal
    met_count = len(conditions_met)
    has_signal = ema_aligned and pullback_ok and met_count >= 3

    if met_count >= 4:
        strength = 'Strong'
    elif met_count >= 3:
        strength = 'Moderate'
    else:
        strength = 'Weak'

    # Stop loss: tighter of 1.5×ATR below entry or candle low
    stop_atr = close - (1.5 * atr) if pd.notna(atr) and atr > 0 else close * 0.97
    stop_loss = min(stop_atr, low)

    # Risk and targets
    risk = close - stop_loss
    risk_pct = (risk / close * 100) if close > 0 else 0
    target_1 = close + (2 * risk)  # 2:1 R:R
    target_2 = close + (3 * risk)  # 3:1 R:R

    rsi_val = float(last.get('RSI', np.nan))

    return {
        'has_signal': has_signal,
        'strategy': 'Trend Following',
        'direction': 'Bullish',
        'strength': strength,
        'conditions_met': conditions_met,
        'conditions_missing': conditions_missing,
        'entry_price': round(close, 2),
        'ema20': round(ema20, 2),
        'stop_loss': round(stop_loss, 2),
        'target_1': round(target_1, 2),
        'target_2': round(target_2, 2),
        'risk_pct': round(risk_pct, 2),
        'pullback_pct': round(pullback_pct, 2),
        'details': {
            'ema50': round(ema50, 2),
            'ema200': round(ema200, 2),
            'adx': round(adx, 1) if pd.notna(adx) else None,
            'rsi': round(rsi_val, 1) if pd.notna(rsi_val) else None,
            'volume_ratio': round(vol_ratio, 1) if pd.notna(vol_ratio) else None,
            'atr': round(atr, 2) if pd.notna(atr) else None,
            'bull_patterns': bull_patterns,
            'is_green': is_green,
            'body_pct': round(body_pct, 1),
        },
    }


def _check_bearish_trend_following_entry(enriched: pd.DataFrame, signals: dict) -> dict:
    """Check Bearish Trend Following entry conditions (short/sell):
    1. EMA alignment (required): EMA200 > EMA50 > EMA20 > close
    2. Rally to EMA20 (required): within 2% below EMA20 or High touched EMA20
    3. Bearish candle (confirmation): red + body > 40%, or bearish pattern
    4. Volume (confirmation): ratio >= 1.5x
    5. ADX (confirmation): >= 25
    """
    last = enriched.iloc[-1]
    conditions_met = []
    conditions_missing = []

    close = float(last['Close'])
    low = float(last['Low'])
    high = float(last['High'])
    open_ = float(last['Open'])
    ema20 = float(last.get('EMA_20', np.nan))
    ema50 = float(last.get('EMA_50', np.nan))
    ema200 = float(last.get('EMA_200', np.nan))
    adx = float(last.get('ADX', np.nan))
    vol_ratio = float(last.get('Volume_Ratio', np.nan))
    atr = float(last.get('ATR', np.nan))

    # Guard against NaN
    if pd.isna(ema20) or pd.isna(ema50) or pd.isna(ema200) or ema20 <= 0:
        return {**_NO_SIGNAL, 'strategy': 'Trend Following', 'direction': 'Bearish'}

    # Condition 1: Bearish EMA alignment
    ema_aligned = ema200 > ema50 > ema20 > close
    if ema_aligned:
        conditions_met.append('EMA aligned (200 > 50 > 20 > price)')
    else:
        conditions_missing.append('Bearish EMA alignment')

    # Condition 2: Rally to EMA20 from below
    pullback_pct = ((ema20 - close) / ema20) * 100  # positive = below EMA20
    ema_touched = close <= ema20 <= high  # rallied into EMA20 intraday but closed below
    near_ema = 0 <= pullback_pct <= ENTRY_EMA_PULLBACK_PCT
    pullback_ok = near_ema or ema_touched

    if pullback_ok:
        detail = f'Rally {pullback_pct:.1f}% to EMA20'
        if ema_touched:
            detail += ' (rejected at EMA20)'
        conditions_met.append(detail)
    else:
        conditions_missing.append(f'Rally to EMA20 ({pullback_pct:.1f}% away)')

    # Condition 3: Bearish candle confirmation
    is_red = close < open_
    candle_range = high - low
    body_pct = (abs(close - open_) / candle_range * 100) if candle_range > 0 else 0

    bear_patterns = []
    try:
        from screener.candlestick_patterns import scan_all_patterns
        patterns = scan_all_patterns(enriched)
        bear_patterns = [p for p, s in patterns.items() if s == 'bearish']
    except Exception:
        pass

    if is_red and body_pct > 40:
        detail = 'Bearish candle'
        if bear_patterns:
            detail += f' + {", ".join(bear_patterns[:2])}'
        conditions_met.append(detail)
    elif bear_patterns:
        conditions_met.append(f'Bearish pattern: {", ".join(bear_patterns[:2])}')
    else:
        conditions_missing.append('Bearish candle confirmation')

    # Condition 4: Volume
    if pd.notna(vol_ratio) and vol_ratio >= ENTRY_VOLUME_RATIO_PREFERRED:
        conditions_met.append(f'Volume confirmed ({vol_ratio:.1f}x avg)')
    else:
        vol_str = f'{vol_ratio:.1f}x' if pd.notna(vol_ratio) else 'N/A'
        conditions_missing.append(f'Volume ({vol_str} avg, need {ENTRY_VOLUME_RATIO_PREFERRED}x)')

    # Condition 5: ADX
    if pd.notna(adx) and adx >= ENTRY_ADX_MIN:
        conditions_met.append(f'ADX strong ({adx:.0f})')
    else:
        adx_str = f'{adx:.0f}' if pd.notna(adx) else 'N/A'
        conditions_missing.append(f'ADX >= {ENTRY_ADX_MIN} (currently {adx_str})')

    # Determine signal
    met_count = len(conditions_met)
    has_signal = ema_aligned and pullback_ok and met_count >= 3

    if met_count >= 4:
        strength = 'Strong'
    elif met_count >= 3:
        strength = 'Moderate'
    else:
        strength = 'Weak'

    # Stop loss: tighter of 1.5×ATR above entry or candle high
    stop_atr = close + (1.5 * atr) if pd.notna(atr) and atr > 0 else close * 1.03
    stop_loss = max(stop_atr, high)

    # Risk and targets (short side: targets are below entry)
    risk = stop_loss - close
    risk_pct = (risk / close * 100) if close > 0 else 0
    target_1 = close - (2 * risk)  # 2:1 R:R
    target_2 = close - (3 * risk)  # 3:1 R:R

    rsi_val = float(last.get('RSI', np.nan))

    return {
        'has_signal': has_signal,
        'strategy': 'Trend Following',
        'direction': 'Bearish',
        'strength': strength,
        'conditions_met': conditions_met,
        'conditions_missing': conditions_missing,
        'entry_price': round(close, 2),
        'ema20': round(ema20, 2),
        'stop_loss': round(stop_loss, 2),
        'target_1': round(target_1, 2),
        'target_2': round(target_2, 2),
        'risk_pct': round(risk_pct, 2),
        'pullback_pct': round(pullback_pct, 2),
        'details': {
            'ema50': round(ema50, 2),
            'ema200': round(ema200, 2),
            'adx': round(adx, 1) if pd.notna(adx) else None,
            'rsi': round(rsi_val, 1) if pd.notna(rsi_val) else None,
            'volume_ratio': round(vol_ratio, 1) if pd.notna(vol_ratio) else None,
            'atr': round(atr, 2) if pd.notna(atr) else None,
            'bear_patterns': bear_patterns,
            'is_red': is_red,
            'body_pct': round(body_pct, 1),
        },
    }


# ── Alert Generation ──────────────────────────────────────────────────────

def generate_alerts(
    data: Dict[str, pd.DataFrame],
    min_score: int = 3,
    index_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    # Pre-compute relative strength for all symbols
    rs_map = compute_relative_strength(data, index_df)

    rows = []
    for sym, df in data.items():
        if len(df) < 50:
            continue
        try:
            result = score_stock(df)
        except Exception:
            continue

        max_score = max(result['bullish_score'], result['bearish_score'])
        if max_score < min_score:
            continue

        direction = 'Bullish' if result['bullish_score'] >= result['bearish_score'] else 'Bearish'

        top_criteria = [c['criterion'] for c in result['criteria']
                        if c['signal'] in (direction.lower(), 'confirmation')]

        # Combo recommendation
        combo_rec = recommend_combo(
            criteria=result['criteria'],
            signals=result['signals'],
            patterns=result['patterns'],
            is_breakout=result['is_breakout'],
            is_breakdown=result['is_breakdown'],
        )

        # Detected patterns matching direction
        if direction == 'Bullish':
            pat_list = [p for p, s in result['patterns'].items() if s == 'bullish']
        else:
            pat_list = [p for p, s in result['patterns'].items() if s == 'bearish']
        pattern_str = ', '.join(pat_list[:3]) if pat_list else 'None'

        # Candle close quality
        close_pct = result.get('close_pct', 0.5)
        body_pct = result.get('body_pct', 0.0)
        is_green = result.get('is_green', True)

        # Determine if this is a "clean close" confirming the direction
        if direction == 'Bullish':
            clean = close_pct >= 0.67 and body_pct >= 0.40 and is_green
        else:
            clean = close_pct <= 0.33 and body_pct >= 0.40 and not is_green

        rows.append({
            'Symbol': sym,
            'Direction': direction,
            'Score': max_score,
            'Bullish': result['bullish_score'],
            'Bearish': result['bearish_score'],
            'RS %': rs_map.get(sym),
            'Close %': round(close_pct * 100),
            'Clean': clean,
            'Top Criteria': ', '.join(top_criteria[:5]),
            'Pattern': pattern_str,
            'Combo': combo_rec['combo'],
        })

    df_alerts = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['Symbol', 'Direction', 'Score', 'Bullish', 'Bearish',
                 'RS %', 'Close %', 'Clean', 'Top Criteria', 'Pattern', 'Combo'])
    if not df_alerts.empty:
        df_alerts = df_alerts.sort_values('Score', ascending=False).reset_index(drop=True)
    return df_alerts
