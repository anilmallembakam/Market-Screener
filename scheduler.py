"""Scheduler for automatic alert saving after market close."""
import json
import pandas as pd
from datetime import datetime, time
from pathlib import Path
from typing import Dict, Optional
import pytz

from screener.stock_lists import get_stock_list
from screener.data_fetcher import fetch_batch
from screener.alerts import generate_alerts
from screener.alert_history import save_alerts, load_history, save_history
from screener.config import DEFAULT_LOOKBACK_DAYS


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

# Scheduler state file
_SCHEDULER_DIR = Path(__file__).resolve().parent.parent / '.alert_history'
_SCHEDULER_FILE = _SCHEDULER_DIR / 'scheduler_state.json'


def _load_scheduler_state() -> dict:
    """Load scheduler state from file."""
    if not _SCHEDULER_FILE.exists():
        return {'last_run': {}}
    try:
        return json.loads(_SCHEDULER_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {'last_run': {}}


def _save_scheduler_state(state: dict) -> None:
    """Save scheduler state to file."""
    _SCHEDULER_DIR.mkdir(parents=True, exist_ok=True)
    _SCHEDULER_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')


def is_market_closed(market: str) -> bool:
    """Check if market is closed for the day."""
    timing = MARKET_TIMINGS.get(market.lower())
    if not timing:
        return False

    tz = pytz.timezone(timing['timezone'])
    now = datetime.now(tz)
    close_time = time(timing['close_hour'], timing['close_minute'])

    # Market is closed if current time is past close time
    return now.time() >= close_time


def should_run_auto_save(market: str) -> bool:
    """Check if auto-save should run for this market today."""
    state = _load_scheduler_state()
    today = datetime.now().strftime('%Y-%m-%d')

    last_run = state.get('last_run', {}).get(market.lower())

    # Already ran today
    if last_run == today:
        return False

    # Check if market is closed
    return is_market_closed(market)


def run_auto_save(market: str, min_score: int = 5) -> int:
    """
    Run automatic alert generation and save for a market.
    Returns number of alerts saved.
    """
    market = market.lower()

    # Check if we should run
    if not should_run_auto_save(market):
        return 0

    # Get stock list based on market
    if market == 'indian':
        symbols, _ = get_stock_list('indian', 'nifty200')
    else:
        symbols, _ = get_stock_list('us', 'sp500')

    if not symbols:
        return 0

    # Fetch data
    daily_data = fetch_batch(symbols, period_days=DEFAULT_LOOKBACK_DAYS, interval='1d')

    if not daily_data:
        return 0

    # Generate alerts
    alerts_df = generate_alerts(daily_data, min_score=min_score)

    if alerts_df.empty:
        return 0

    # Save alerts
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
