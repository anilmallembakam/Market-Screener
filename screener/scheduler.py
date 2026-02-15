"""Scheduler for automatic alert saving after market close."""
import pandas as pd
from datetime import datetime, time
from typing import Dict, Optional
import pytz

from screener.stock_lists import get_stock_list
from screener.data_fetcher import fetch_batch
from screener.alerts import generate_alerts
from screener.alert_history import save_alerts
from screener.config import DEFAULT_LOOKBACK_DAYS
from screener.db import db_get_scheduler_state, db_set_scheduler_last_run


# Market timings
MARKET_TIMINGS = {
    'us': {
        'timezone': 'America/New_York',
        'close_hour': 16,
        'close_minute': 0,
    },
    'indian': {
        'timezone': 'Asia/Kolkata',
        'close_hour': 15,
        'close_minute': 30,
    }
}


def _load_scheduler_state() -> dict:
    """Load scheduler state from SQLite."""
    return {'last_run': db_get_scheduler_state()}


def _save_scheduler_state(state: dict) -> None:
    """Save scheduler state to SQLite."""
    for market, date_str in state.get('last_run', {}).items():
        db_set_scheduler_last_run(market, date_str)


def is_market_closed(market: str) -> bool:
    """Check if market is closed for the day."""
    timing = MARKET_TIMINGS.get(market.lower())
    if not timing:
        return False

    tz = pytz.timezone(timing['timezone'])
    now = datetime.now(tz)
    close_time = time(timing['close_hour'], timing['close_minute'])

    return now.time() >= close_time


def should_run_auto_save(market: str) -> bool:
    """Check if auto-save should run for this market today."""
    state = _load_scheduler_state()
    today = datetime.now().strftime('%Y-%m-%d')

    last_run = state.get('last_run', {}).get(market.lower())

    if last_run == today:
        return False

    return is_market_closed(market)


def run_auto_save(market: str, min_score: int = 5) -> int:
    """Run automatic alert generation and save for a market.
    Returns number of alerts saved."""
    market = market.lower()

    if not should_run_auto_save(market):
        return 0

    if market == 'indian':
        symbols, _ = get_stock_list('indian', 'nifty200')
    else:
        symbols, _ = get_stock_list('us', 'sp500')

    if not symbols:
        return 0

    daily_data = fetch_batch(symbols, period_days=DEFAULT_LOOKBACK_DAYS, interval='1d')

    if not daily_data:
        return 0

    alerts_df = generate_alerts(daily_data, min_score=min_score)

    if alerts_df.empty:
        return 0

    saved = save_alerts(alerts_df, daily_data, market)

    # Update scheduler state
    state = _load_scheduler_state()
    if 'last_run' not in state:
        state['last_run'] = {}
    state['last_run'][market] = datetime.now().strftime('%Y-%m-%d')
    _save_scheduler_state(state)

    return saved


def run_all_markets_auto_save(min_score: int = 5) -> Dict[str, int]:
    """Run auto-save for all markets. Returns dict of market -> count saved."""
    results = {}
    for market in ['us', 'indian']:
        results[market] = run_auto_save(market, min_score)
    return results


def get_last_auto_save_times() -> Dict[str, Optional[str]]:
    """Get last auto-save times for each market."""
    state = _load_scheduler_state()
    return {
        'us': state.get('last_run', {}).get('us'),
        'indian': state.get('last_run', {}).get('indian'),
    }
