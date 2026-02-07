import pandas as pd
import numpy as np
from typing import Dict
from screener.candlestick_patterns import scan_all_patterns
from screener.technical_indicators import compute_all, generate_signals
from screener.breakout_detector import is_breaking_out, is_breaking_down


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

    return {
        'bullish_score': bullish,
        'bearish_score': bearish,
        'criteria': criteria,
        'patterns': patterns,
        'signals': signals,
        'is_breakout': breakout,
        'is_breakdown': breakdown,
    }


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


# ── Alert Generation ──────────────────────────────────────────────────────

def generate_alerts(data: Dict[str, pd.DataFrame], min_score: int = 3) -> pd.DataFrame:
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

        rows.append({
            'Symbol': sym,
            'Direction': direction,
            'Score': max_score,
            'Bullish': result['bullish_score'],
            'Bearish': result['bearish_score'],
            'Top Criteria': ', '.join(top_criteria[:5]),
            'Pattern': pattern_str,
            'Combo': combo_rec['combo'],
        })

    df_alerts = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['Symbol', 'Direction', 'Score', 'Bullish', 'Bearish',
                 'Top Criteria', 'Pattern', 'Combo'])
    if not df_alerts.empty:
        df_alerts = df_alerts.sort_values('Score', ascending=False).reset_index(drop=True)
    return df_alerts
