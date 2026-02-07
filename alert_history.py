"""Alert history storage and performance tracking."""
import json
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
import streamlit as st

# Storage path
_HISTORY_DIR = Path(__file__).resolve().parent.parent / '.alert_history'
_HISTORY_FILE = _HISTORY_DIR / 'alerts.json'


def _ensure_dir():
    """Ensure history directory exists."""
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def load_history() -> List[dict]:
    """Load alert history from JSON file."""
    if not _HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(_HISTORY_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(history: List[dict]) -> None:
    """Save alert history to JSON file."""
    _ensure_dir()
    try:
        _HISTORY_FILE.write_text(
            json.dumps(history, default=str, indent=2),
            encoding='utf-8'
        )
    except Exception:
        pass


def save_alerts(alerts_df: pd.DataFrame, daily_data: Dict[str, pd.DataFrame], market: str = 'us') -> int:
    """Save current alerts to history. Returns number of new alerts saved."""
    if alerts_df.empty:
        return 0

    history = load_history()
    today = datetime.now().strftime('%Y-%m-%d')

    # Get existing symbols for today to avoid duplicates
    existing_today = {
        (a['symbol'], a['date']) for a in history
    }

    new_count = 0
    for _, row in alerts_df.iterrows():
        symbol = row['Symbol']
        key = (symbol, today)

        if key in existing_today:
            continue  # Skip duplicate

        # Get alert price from daily_data
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
            'market': market.lower(),  # 'us' or 'indian'
        }
        history.append(alert_record)
        new_count += 1

    if new_count > 0:
        save_history(history)

    return new_count


def get_historical_alerts(days_back: int = 30, market: str = None, direction: str = None) -> pd.DataFrame:
    """Get alerts from the last N days with optional market and direction filters."""
    history = load_history()
    if not history:
        return pd.DataFrame()

    cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    filtered = [a for a in history if a.get('date', '') >= cutoff]

    # Apply market filter
    if market and market != 'all':
        filtered = [a for a in filtered if a.get('market', 'us').lower() == market.lower()]

    # Apply direction filter
    if direction and direction != 'all':
        filtered = [a for a in filtered if a.get('direction', '').lower() == direction.lower()]

    if not filtered:
        return pd.DataFrame()

    return pd.DataFrame(filtered)


def delete_alert(symbol: str, date: str) -> bool:
    """Delete a specific alert from history."""
    history = load_history()
    original_len = len(history)
    history = [a for a in history if not (a['symbol'] == symbol and a['date'] == date)]

    if len(history) < original_len:
        save_history(history)
        return True
    return False


def clear_old_alerts(days_to_keep: int = 60) -> int:
    """Remove alerts older than N days. Returns count of removed alerts."""
    history = load_history()
    cutoff = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')

    original_len = len(history)
    history = [a for a in history if a.get('date', '') >= cutoff]

    removed = original_len - len(history)
    if removed > 0:
        save_history(history)

    return removed


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_performance_data(symbol: str, start_date: str, days: int = 20) -> Optional[pd.DataFrame]:
    """Fetch price data from alert date to track performance."""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = start + timedelta(days=days + 5)  # Extra days for weekends

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

    # Calculate P&L based on direction
    if direction == 'Bullish':
        pnl_pct = ((current_price - alert_price) / alert_price) * 100
        max_gain_pct = ((max(highs) - alert_price) / alert_price) * 100
        max_drawdown_pct = ((min(lows) - alert_price) / alert_price) * 100
    else:  # Bearish
        pnl_pct = ((alert_price - current_price) / alert_price) * 100
        max_gain_pct = ((alert_price - min(lows)) / alert_price) * 100
        max_drawdown_pct = ((alert_price - max(highs)) / alert_price) * 100

    # Determine status
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

    # Detect momentum loss (losing steam)
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

    # Calculate short-term and medium-term returns
    recent_5d = closes[-1] / closes[-5] - 1 if len(closes) >= 5 else 0

    if len(closes) >= 10:
        prev_5d = closes[-5] / closes[-10] - 1
    else:
        prev_5d = recent_5d

    if direction == 'Bullish':
        if recent_5d < -0.03:  # Down more than 3% in last 5 days
            return 'Losing Steam'
        elif recent_5d < prev_5d - 0.02:  # Momentum slowing
            return 'Slowing'
        elif recent_5d > 0.02:
            return 'Strong'
        else:
            return 'Stable'
    else:  # Bearish
        if recent_5d > 0.03:  # Up more than 3% (bad for bearish)
            return 'Losing Steam'
        elif recent_5d > prev_5d + 0.02:
            return 'Slowing'
        elif recent_5d < -0.02:
            return 'Strong'
        else:
            return 'Stable'


def get_alerts_by_date(date_str: str, market: str = None) -> pd.DataFrame:
    """Get alerts for a specific date."""
    history = load_history()
    if not history:
        return pd.DataFrame()

    filtered = [a for a in history if a.get('date', '') == date_str]

    if market and market != 'all':
        filtered = [a for a in filtered if a.get('market', 'us').lower() == market.lower()]

    return pd.DataFrame(filtered) if filtered else pd.DataFrame()


def get_alerts_date_range(start_date: str, end_date: str, market: str = None) -> pd.DataFrame:
    """Get alerts within a date range."""
    history = load_history()
    if not history:
        return pd.DataFrame()

    filtered = [
        a for a in history
        if start_date <= a.get('date', '') <= end_date
    ]

    if market and market != 'all':
        filtered = [a for a in filtered if a.get('market', 'us').lower() == market.lower()]

    return pd.DataFrame(filtered) if filtered else pd.DataFrame()


def get_available_dates() -> list:
    """Get list of all dates that have alerts."""
    history = load_history()
    if not history:
        return []

    dates = sorted(set(a.get('date', '') for a in history if a.get('date')), reverse=True)
    return dates


def get_weekly_summary(weeks_back: int = 1, market: str = None) -> dict:
    """
    Generate weekly performance summary.
    Returns stats for alerts from the past N weeks.
    """
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

    # Calculate performance for each alert
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

    # Calculate stats
    winners = len(perf_df[perf_df['pnl_pct'] >= 5])
    losers = len(perf_df[perf_df['pnl_pct'] <= -5])
    total = len(perf_df)

    # Best and worst performers
    best_idx = perf_df['pnl_pct'].idxmax() if not perf_df.empty else None
    worst_idx = perf_df['pnl_pct'].idxmin() if not perf_df.empty else None

    best = perf_df.loc[best_idx].to_dict() if best_idx is not None else None
    worst = perf_df.loc[worst_idx].to_dict() if worst_idx is not None else None

    # Group by direction
    by_direction = {}
    for direction in perf_df['direction'].unique():
        dir_df = perf_df[perf_df['direction'] == direction]
        by_direction[direction] = {
            'count': len(dir_df),
            'avg_pnl': round(dir_df['pnl_pct'].mean(), 2),
            'win_rate': round(len(dir_df[dir_df['pnl_pct'] >= 5]) / len(dir_df) * 100, 1) if len(dir_df) > 0 else 0
        }

    # Group by market
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
