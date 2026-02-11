"""Watchlist storage - curated list of stocks to monitor.
Uses Google Sheets for cloud storage with local JSON fallback."""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import streamlit as st


# Storage path (fallback)
_HISTORY_DIR = Path(__file__).resolve().parent.parent / '.alert_history'
_WATCHLIST_FILE = _HISTORY_DIR / 'watchlist.json'


def _use_gsheet() -> bool:
    """Check if Google Sheets is configured and should be used."""
    try:
        from screener.gsheet_storage import is_gsheet_configured
        return is_gsheet_configured()
    except Exception:
        return False


def _ensure_dir():
    """Ensure history directory exists."""
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _load_local() -> List[dict]:
    """Load watchlist from local JSON file."""
    if not _WATCHLIST_FILE.exists():
        return []
    try:
        data = json.loads(_WATCHLIST_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_local(watchlist: List[dict]) -> None:
    """Save watchlist to local JSON file."""
    _ensure_dir()
    try:
        _WATCHLIST_FILE.write_text(
            json.dumps(watchlist, default=str, indent=2),
            encoding='utf-8'
        )
    except Exception:
        pass


def load_watchlist() -> List[dict]:
    """Load all watchlist items from storage (Google Sheets or local JSON)."""
    if _use_gsheet():
        try:
            from screener.gsheet_storage import load_watchlist_gsheet
            return load_watchlist_gsheet()
        except Exception as e:
            st.warning(f"Google Sheets error, falling back to local: {e}")

    return _load_local()


def is_in_watchlist(symbol: str) -> bool:
    """Check if a symbol is already in the watchlist."""
    watchlist = load_watchlist()
    return any(item.get('symbol', '') == symbol for item in watchlist)


def add_to_watchlist(symbol: str, direction: str, score: int, alert_price: float,
                     criteria: str, pattern: str, combo: str, market: str,
                     notes: str = "") -> bool:
    """Add a stock to the watchlist. Returns True if added, False if already exists."""
    today = datetime.now().strftime('%Y-%m-%d')
    item = {
        'symbol': symbol,
        'date_added': today,
        'direction': direction,
        'score': int(score),
        'alert_price': float(alert_price),
        'criteria': criteria,
        'pattern': pattern,
        'combo': combo,
        'market': market.lower(),
        'notes': notes,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    # Try Google Sheets first
    if _use_gsheet():
        try:
            from screener.gsheet_storage import save_watchlist_item_gsheet
            return save_watchlist_item_gsheet(item)
        except Exception as e:
            st.warning(f"Google Sheets error: {e}. Saving to local file.")

    # Fallback to local JSON
    watchlist = _load_local()
    existing_symbols = {w.get('symbol', '') for w in watchlist}
    if symbol in existing_symbols:
        return False

    watchlist.append(item)
    _save_local(watchlist)
    return True


def remove_from_watchlist(symbol: str) -> bool:
    """Remove a stock from the watchlist. Returns True if removed."""
    # Try Google Sheets first
    if _use_gsheet():
        try:
            from screener.gsheet_storage import remove_watchlist_item_gsheet
            return remove_watchlist_item_gsheet(symbol)
        except Exception as e:
            st.warning(f"Google Sheets error: {e}. Removing from local file.")

    # Fallback to local JSON
    watchlist = _load_local()
    original_len = len(watchlist)
    watchlist = [w for w in watchlist if w.get('symbol', '') != symbol]

    if len(watchlist) < original_len:
        _save_local(watchlist)
        return True
    return False


def update_watchlist_notes(symbol: str, notes: str) -> bool:
    """Update notes for a watchlist item. Returns True if updated."""
    # Try Google Sheets first
    if _use_gsheet():
        try:
            from screener.gsheet_storage import get_watchlist_worksheet
            ws = get_watchlist_worksheet()
            if ws:
                records = ws.get_all_records()
                for i, record in enumerate(records, start=2):
                    if record.get('symbol', '') == symbol:
                        # notes is column 10 (1-indexed)
                        ws.update_cell(i, 10, notes)
                        return True
            return False
        except Exception as e:
            st.warning(f"Google Sheets error: {e}. Updating local file.")

    # Fallback to local JSON
    watchlist = _load_local()
    for item in watchlist:
        if item.get('symbol', '') == symbol:
            item['notes'] = notes
            _save_local(watchlist)
            return True
    return False
