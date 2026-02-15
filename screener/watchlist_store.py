"""Watchlist storage - curated list of stocks to monitor.
Uses SQLite for persistent local storage."""
from datetime import datetime
from typing import List
import streamlit as st

from screener.db import db_load_watchlist, db_add_watchlist_item, db_remove_watchlist_item


def load_watchlist() -> List[dict]:
    """Load all watchlist items from SQLite.
    Uses Streamlit session_state cache to avoid repeated DB reads within the same rerun."""
    if hasattr(st, 'session_state') and '_watchlist_cache' in st.session_state:
        return st.session_state['_watchlist_cache']

    result = db_load_watchlist()
    if hasattr(st, 'session_state'):
        st.session_state['_watchlist_cache'] = result
    return result


def _invalidate_cache():
    """Clear the session_state watchlist cache after modifications."""
    if hasattr(st, 'session_state') and '_watchlist_cache' in st.session_state:
        del st.session_state['_watchlist_cache']


def get_watchlist_symbols() -> set:
    """Get set of all symbols in watchlist. Efficient for batch lookups."""
    watchlist = load_watchlist()
    return {item.get('symbol', '') for item in watchlist}


def is_in_watchlist(symbol: str) -> bool:
    """Check if a symbol is already in the watchlist."""
    return symbol in get_watchlist_symbols()


def add_to_watchlist(symbol: str, direction: str, score: int, alert_price: float,
                     criteria: str, pattern: str, combo: str, market: str,
                     alert_date: str = "") -> bool:
    """Add a stock to the watchlist. Returns True if added, False if already exists."""
    today = datetime.now().strftime('%Y-%m-%d')
    item = {
        'symbol': symbol,
        'date_added': today,
        'alert_date': alert_date or today,
        'direction': direction,
        'score': int(score),
        'alert_price': float(alert_price),
        'criteria': criteria,
        'pattern': pattern,
        'combo': combo,
        'market': market.lower(),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    result = db_add_watchlist_item(item)
    if result:
        _invalidate_cache()
    return result


def remove_from_watchlist(symbol: str) -> bool:
    """Remove a stock from the watchlist. Returns True if removed."""
    result = db_remove_watchlist_item(symbol)
    if result:
        _invalidate_cache()
    return result
