"""Alert history storage and performance tracking.
Uses SQLite for persistent local storage."""
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import streamlit as st

from screener.db import (
    db_load_all_alerts,
    db_save_alerts_batch,
    db_get_historical_alerts,
    db_get_alerts_by_date,
    db_get_alerts_date_range,
    db_get_available_dates,
    db_delete_alert,
    db_clear_old_alerts,
)


def load_history() -> List[dict]:
    """Load all alert history from storage."""
    return db_load_all_alerts()


def save_history(history: List[dict]) -> None:
    """Legacy function - no longer needed with SQLite."""
    pass


def save_alerts(alerts_df: pd.DataFrame, daily_data: Dict[str, pd.DataFrame], market: str = 'us') -> int:
    """Save current alerts to history. Returns number of new alerts saved."""
    if alerts_df.empty:
        return 0

    today = datetime.now().strftime('%Y-%m-%d')

    alerts_to_save = []
    for _, row in alerts_df.iterrows():
        symbol = row['Symbol']

        alert_price = 0.0
        if symbol in daily_data and not daily_data[symbol].empty:
            alert_price = float(daily_data[symbol]['Close'].iloc[-1])

        alert_record = {
            'symbol': symbol,
            'date': today,
            'direction': row['Direction'],
            'score': int(row['Score']),
            'alert_price': alert_price,
            'criteria': row.get('Top Criteria', ''),
            'pattern': row.get('Pattern', ''),
            'combo': row.get('Combo', ''),
            'market': market.lower(),
        }
        alerts_to_save.append(alert_record)

    return db_save_alerts_batch(alerts_to_save)


def get_historical_alerts(days_back: int = 30, market: str = None, direction: str = None) -> pd.DataFrame:
    """Get alerts from the last N days with optional market and direction filters."""
    rows = db_get_historical_alerts(days_back, market, direction)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def delete_alert(symbol: str, date: str) -> bool:
    """Delete a specific alert from history."""
    return db_delete_alert(symbol, date)


def clear_old_alerts(days_to_keep: int = 60) -> int:
    """Remove alerts older than N days. Returns count of removed alerts."""
    return db_clear_old_alerts(days_to_keep)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_performance_data(symbol: str, start_date: str, days: int = 20) -> Optional[pd.DataFrame]:
    """Fetch price data from alert date to track performance."""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = start + timedelta(days=days + 5)

        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end)

        if df.empty:
            return None

        return df[['Open', 'High', 'Low', 'Close', 'Volume']].head(days)
    except Exception:
        return None


def calculate_performance(alert: dict, price_data: pd.DataFrame) -> dict:
    """Calculate performance metrics for an alert."""
    if price_data is None or price_data.empty:
        return {
            'current_price': 0,
            'pnl_pct': 0,
            'max_gain_pct': 0,
            'max_drawdown_pct': 0,
            'days_tracked': 0,
            'status': 'No Data',
            'momentum': 'Unknown',
        }

    alert_price = alert.get('alert_price', 0)
    if alert_price <= 0:
        alert_price = float(price_data['Close'].iloc[0])

    direction = alert.get('direction', 'Bullish')
    closes = price_data['Close'].values
    highs = price_data['High'].values
    lows = price_data['Low'].values

    current_price = float(closes[-1])
    days_tracked = len(closes)

    if direction == 'Bullish':
        pnl_pct = ((current_price - alert_price) / alert_price) * 100
        max_gain_pct = ((max(highs) - alert_price) / alert_price) * 100
        max_drawdown_pct = ((min(lows) - alert_price) / alert_price) * 100
    else:
        pnl_pct = ((alert_price - current_price) / alert_price) * 100
        max_gain_pct = ((alert_price - min(lows)) / alert_price) * 100
        max_drawdown_pct = ((alert_price - max(highs)) / alert_price) * 100

    if pnl_pct >= 10:
        status = 'Winner'
    elif pnl_pct >= 5:
        status = 'Gaining'
    elif pnl_pct >= 0:
        status = 'Flat'
    elif pnl_pct >= -5:
        status = 'Slight Loss'
    else:
        status = 'Loser'

    momentum = _detect_momentum(closes, direction)

    return {
        'current_price': round(current_price, 2),
        'pnl_pct': round(pnl_pct, 2),
        'max_gain_pct': round(max_gain_pct, 2),
        'max_drawdown_pct': round(max_drawdown_pct, 2),
        'days_tracked': days_tracked,
        'status': status,
        'momentum': momentum,
    }


def _detect_momentum(closes: list, direction: str) -> str:
    """Detect if the stock is losing momentum."""
    if len(closes) < 5:
        return 'Too Early'

    recent_5d = closes[-1] / closes[-5] - 1 if len(closes) >= 5 else 0

    if len(closes) >= 10:
        prev_5d = closes[-5] / closes[-10] - 1
    else:
        prev_5d = recent_5d

    if direction == 'Bullish':
        if recent_5d < -0.03:
            return 'Losing Steam'
        elif recent_5d < prev_5d - 0.02:
            return 'Slowing'
        elif recent_5d > 0.02:
            return 'Strong'
        else:
            return 'Stable'
    else:
        if recent_5d > 0.03:
            return 'Losing Steam'
        elif recent_5d > prev_5d + 0.02:
            return 'Slowing'
        elif recent_5d < -0.02:
            return 'Strong'
        else:
            return 'Stable'


def get_alerts_by_date(date_str: str, market: str = None) -> pd.DataFrame:
    """Get alerts for a specific date."""
    rows = db_get_alerts_by_date(date_str, market)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_alerts_date_range(start_date: str, end_date: str, market: str = None) -> pd.DataFrame:
    """Get alerts within a date range."""
    rows = db_get_alerts_date_range(start_date, end_date, market)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def get_available_dates() -> list:
    """Get list of all dates that have alerts."""
    return db_get_available_dates()


def get_weekly_summary(weeks_back: int = 1, market: str = None) -> dict:
    """Generate weekly performance summary."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7 * weeks_back)

    alerts_df = get_alerts_date_range(
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d'),
        market
    )

    if alerts_df.empty:
        return {
            'total_alerts': 0,
            'winners': 0,
            'losers': 0,
            'win_rate': 0,
            'avg_pnl': 0,
            'best_performer': None,
            'worst_performer': None,
            'by_direction': {},
            'by_market': {},
            'losing_steam_count': 0,
        }

    performance_list = []
    for _, alert in alerts_df.iterrows():
        price_data = fetch_performance_data(alert['symbol'], alert['date'], 20)
        perf = calculate_performance(alert.to_dict(), price_data)
        perf['symbol'] = alert['symbol']
        perf['direction'] = alert.get('direction', 'N/A')
        perf['market'] = alert.get('market', 'us')
        perf['date'] = alert['date']
        performance_list.append(perf)

    perf_df = pd.DataFrame(performance_list)

    winners = len(perf_df[perf_df['pnl_pct'] >= 5])
    losers = len(perf_df[perf_df['pnl_pct'] <= -5])
    total = len(perf_df)

    best_idx = perf_df['pnl_pct'].idxmax() if not perf_df.empty else None
    worst_idx = perf_df['pnl_pct'].idxmin() if not perf_df.empty else None

    best = perf_df.loc[best_idx].to_dict() if best_idx is not None else None
    worst = perf_df.loc[worst_idx].to_dict() if worst_idx is not None else None

    by_direction = {}
    for direction in perf_df['direction'].unique():
        dir_df = perf_df[perf_df['direction'] == direction]
        by_direction[direction] = {
            'count': len(dir_df),
            'avg_pnl': round(dir_df['pnl_pct'].mean(), 2),
            'win_rate': round(len(dir_df[dir_df['pnl_pct'] >= 5]) / len(dir_df) * 100, 1) if len(dir_df) > 0 else 0
        }

    by_market = {}
    for mkt in perf_df['market'].unique():
        mkt_df = perf_df[perf_df['market'] == mkt]
        by_market[mkt.upper()] = {
            'count': len(mkt_df),
            'avg_pnl': round(mkt_df['pnl_pct'].mean(), 2),
            'win_rate': round(len(mkt_df[mkt_df['pnl_pct'] >= 5]) / len(mkt_df) * 100, 1) if len(mkt_df) > 0 else 0
        }

    losing_steam = len(perf_df[perf_df['momentum'] == 'Losing Steam'])

    return {
        'total_alerts': total,
        'winners': winners,
        'losers': losers,
        'win_rate': round(winners / total * 100, 1) if total > 0 else 0,
        'avg_pnl': round(perf_df['pnl_pct'].mean(), 2),
        'best_performer': best,
        'worst_performer': worst,
        'by_direction': by_direction,
        'by_market': by_market,
        'losing_steam_count': losing_steam,
        'period_start': start_date.strftime('%Y-%m-%d'),
        'period_end': end_date.strftime('%Y-%m-%d'),
    }


# ---------------------------------------------------------------------------
# Entry-signal performance (lightweight — no API calls)
# ---------------------------------------------------------------------------

def compute_signal_performance(signal: dict, current_price: float) -> dict:
    """Compute live performance for a persisted entry signal.

    Takes the stored signal dict + a current price and returns P&L,
    days held, and an auto-detected status hint.
    """
    entry = float(signal.get('entry_price', 0))
    direction = signal.get('direction', 'Bullish')
    signal_date = signal.get('signal_date', datetime.now().strftime('%Y-%m-%d'))

    try:
        days_held = (datetime.now() - datetime.strptime(signal_date, '%Y-%m-%d')).days
    except (ValueError, TypeError):
        days_held = 0

    if entry <= 0:
        return {'current_price': current_price, 'pnl_pct': 0,
                'days_held': days_held, 'status_hint': 'Active'}

    if direction == 'Bullish':
        pnl_pct = ((current_price - entry) / entry) * 100
    else:
        pnl_pct = ((entry - current_price) / entry) * 100

    # Auto-detect if stop or target has been breached
    stop = float(signal.get('stop_loss', 0))
    t1 = float(signal.get('target_1', 0))

    if direction == 'Bullish':
        if stop > 0 and current_price <= stop:
            status_hint = 'Stopped Out'
        elif t1 > 0 and current_price >= t1:
            status_hint = 'Target Hit'
        else:
            status_hint = 'Active'
    else:
        if stop > 0 and current_price >= stop:
            status_hint = 'Stopped Out'
        elif t1 > 0 and current_price <= t1:
            status_hint = 'Target Hit'
        else:
            status_hint = 'Active'

    return {
        'current_price': round(current_price, 2),
        'pnl_pct': round(pnl_pct, 2),
        'days_held': days_held,
        'status_hint': status_hint,
    }
