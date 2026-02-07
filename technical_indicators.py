import talib
import numpy as np
import pandas as pd
from typing import Dict
from screener.config import (EMA_PERIODS, RSI_PERIOD, MACD_FAST, MACD_SLOW,
                              MACD_SIGNAL, BB_PERIOD, BB_STD, ADX_PERIOD)


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    o = df['Open'].values.astype(float)
    h = df['High'].values.astype(float)
    l = df['Low'].values.astype(float)
    c = df['Close'].values.astype(float)
    v = df['Volume'].values.astype(float)

    for period in EMA_PERIODS:
        df[f'EMA_{period}'] = talib.EMA(c, timeperiod=period)

    df['RSI'] = talib.RSI(c, timeperiod=RSI_PERIOD)

    macd, macd_sig, macd_hist = talib.MACD(c, fastperiod=MACD_FAST,
                                            slowperiod=MACD_SLOW,
                                            signalperiod=MACD_SIGNAL)
    df['MACD'] = macd
    df['MACD_Signal'] = macd_sig
    df['MACD_Hist'] = macd_hist

    upper, middle, lower = talib.BBANDS(c, timeperiod=BB_PERIOD,
                                         nbdevup=BB_STD, nbdevdn=BB_STD)
    df['BB_Upper'] = upper
    df['BB_Middle'] = middle
    df['BB_Lower'] = lower

    df['ADX'] = talib.ADX(h, l, c, timeperiod=ADX_PERIOD)
    df['Plus_DI'] = talib.PLUS_DI(h, l, c, timeperiod=ADX_PERIOD)
    df['Minus_DI'] = talib.MINUS_DI(h, l, c, timeperiod=ADX_PERIOD)

    # VWAP (cumulative for daily data)
    tp = (h + l + c) / 3
    cumulative_tp_vol = np.cumsum(tp * v)
    cumulative_vol = np.cumsum(v)
    with np.errstate(divide='ignore', invalid='ignore'):
        vwap = np.where(cumulative_vol > 0, cumulative_tp_vol / cumulative_vol, np.nan)
    df['VWAP'] = vwap

    df['Volume_SMA_20'] = talib.SMA(v, timeperiod=20)
    with np.errstate(divide='ignore', invalid='ignore'):
        df['Volume_Ratio'] = np.where(df['Volume_SMA_20'] > 0,
                                       v / df['Volume_SMA_20'].values, np.nan)

    df['ATR'] = talib.ATR(h, l, c, timeperiod=14)

    return df


def generate_signals(df: pd.DataFrame) -> Dict[str, str]:
    last = df.iloc[-1]
    prev = df.iloc[-2]
    signals = {}

    # RSI
    rsi = last.get('RSI', np.nan)
    if pd.notna(rsi):
        if rsi < 30:
            signals['RSI'] = f'Oversold ({rsi:.1f})'
        elif rsi > 70:
            signals['RSI'] = f'Overbought ({rsi:.1f})'
        else:
            signals['RSI'] = f'Neutral ({rsi:.1f})'

    # MACD
    macd_now = last.get('MACD', np.nan)
    macd_sig_now = last.get('MACD_Signal', np.nan)
    macd_prev = prev.get('MACD', np.nan)
    macd_sig_prev = prev.get('MACD_Signal', np.nan)
    if pd.notna(macd_now) and pd.notna(macd_sig_now):
        if macd_now > macd_sig_now and macd_prev <= macd_sig_prev:
            signals['MACD'] = 'Bullish Crossover'
        elif macd_now < macd_sig_now and macd_prev >= macd_sig_prev:
            signals['MACD'] = 'Bearish Crossover'
        elif macd_now > macd_sig_now:
            signals['MACD'] = 'Bullish'
        else:
            signals['MACD'] = 'Bearish'

    # EMA alignment
    c = last.get('Close', np.nan)
    ema20 = last.get('EMA_20', np.nan)
    ema50 = last.get('EMA_50', np.nan)
    ema200 = last.get('EMA_200', np.nan)
    if pd.notna(c) and pd.notna(ema20) and pd.notna(ema50) and pd.notna(ema200):
        if c > ema20 > ema50 > ema200:
            signals['EMA_Trend'] = 'Strong Bullish'
        elif c < ema20 < ema50 < ema200:
            signals['EMA_Trend'] = 'Strong Bearish'
        elif c > ema200:
            signals['EMA_Trend'] = 'Bullish'
        elif c < ema200:
            signals['EMA_Trend'] = 'Bearish'
        else:
            signals['EMA_Trend'] = 'Mixed'

    # Bollinger Bands
    bb_upper = last.get('BB_Upper', np.nan)
    bb_lower = last.get('BB_Lower', np.nan)
    if pd.notna(bb_upper) and pd.notna(bb_lower) and pd.notna(c):
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_pct = (c - bb_lower) / bb_range
            if bb_pct < 0.1:
                signals['BB'] = 'Near Lower Band'
            elif bb_pct > 0.9:
                signals['BB'] = 'Near Upper Band'
            else:
                signals['BB'] = f'Mid-Band ({bb_pct:.0%})'

    # ADX
    adx = last.get('ADX', np.nan)
    plus_di = last.get('Plus_DI', np.nan)
    minus_di = last.get('Minus_DI', np.nan)
    if pd.notna(adx) and pd.notna(plus_di) and pd.notna(minus_di):
        direction = 'Bullish' if plus_di > minus_di else 'Bearish'
        if adx > 25:
            signals['ADX'] = f'Strong {direction} Trend ({adx:.1f})'
        else:
            signals['ADX'] = f'Weak/No Trend ({adx:.1f})'

    # Volume
    vol_ratio = last.get('Volume_Ratio', np.nan)
    if pd.notna(vol_ratio):
        if vol_ratio > 1.5:
            signals['Volume'] = f'High Volume ({vol_ratio:.1f}x avg)'
        elif vol_ratio < 0.5:
            signals['Volume'] = f'Low Volume ({vol_ratio:.1f}x avg)'
        else:
            signals['Volume'] = f'Normal ({vol_ratio:.1f}x avg)'

    return signals


def batch_summary(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for sym, df in data.items():
        try:
            enriched = compute_all(df.copy())
            sigs = generate_signals(enriched)
            last = enriched.iloc[-1]
            rows.append({
                'Symbol': sym,
                'Close': round(float(last['Close']), 2),
                'RSI': round(float(last['RSI']), 1) if pd.notna(last.get('RSI')) else None,
                'MACD': sigs.get('MACD', ''),
                'EMA_Trend': sigs.get('EMA_Trend', ''),
                'ADX': round(float(last['ADX']), 1) if pd.notna(last.get('ADX')) else None,
                'Volume': sigs.get('Volume', ''),
                'BB': sigs.get('BB', ''),
            })
        except Exception:
            continue
    return pd.DataFrame(rows) if rows else pd.DataFrame()
