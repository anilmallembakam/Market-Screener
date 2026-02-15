"""SQLite storage layer for alerts, watchlist, and scheduler state."""
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

_DB_DIR = Path(__file__).resolve().parent.parent / '.alert_history'
_DB_PATH = _DB_DIR / 'screener.db'

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
        _init_schema(_local.conn)
        _maybe_migrate(_local.conn)
    return _local.conn


def _init_schema(conn: sqlite3.Connection):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            direction TEXT NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            alert_price REAL NOT NULL DEFAULT 0.0,
            criteria TEXT DEFAULT '',
            pattern TEXT DEFAULT '',
            combo TEXT DEFAULT '',
            market TEXT DEFAULT 'us',
            created_at TEXT NOT NULL,
            UNIQUE(symbol, date)
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_date ON alerts(date);
        CREATE INDEX IF NOT EXISTS idx_alerts_market ON alerts(market);
        CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol);

        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            date_added TEXT NOT NULL,
            alert_date TEXT DEFAULT '',
            direction TEXT DEFAULT '',
            score INTEGER DEFAULT 0,
            alert_price REAL DEFAULT 0.0,
            criteria TEXT DEFAULT '',
            pattern TEXT DEFAULT '',
            combo TEXT DEFAULT '',
            market TEXT DEFAULT 'us',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scheduler_state (
            market TEXT PRIMARY KEY,
            last_run TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entry_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal_date TEXT NOT NULL,
            direction TEXT NOT NULL,
            strategy TEXT NOT NULL DEFAULT 'Trend Following',
            strength TEXT NOT NULL DEFAULT 'Moderate',
            setup TEXT DEFAULT '',
            entry_price REAL NOT NULL,
            ema20 REAL NOT NULL DEFAULT 0,
            stop_loss REAL NOT NULL,
            target_1 REAL NOT NULL,
            target_2 REAL NOT NULL,
            risk_pct REAL NOT NULL DEFAULT 0,
            pullback_pct REAL NOT NULL DEFAULT 0,
            adx REAL,
            rsi REAL,
            volume_ratio REAL,
            atr REAL,
            conditions_met TEXT DEFAULT '',
            conditions_missing TEXT DEFAULT '',
            source TEXT DEFAULT 'Watchlist',
            market TEXT DEFAULT 'us',
            status TEXT DEFAULT 'Active',
            exit_price REAL,
            exit_date TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(symbol, signal_date, direction)
        );
        CREATE INDEX IF NOT EXISTS idx_entry_signals_status ON entry_signals(status);
        CREATE INDEX IF NOT EXISTS idx_entry_signals_date ON entry_signals(signal_date);
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Migration from JSON files
# ---------------------------------------------------------------------------

def _maybe_migrate(conn: sqlite3.Connection):
    """Auto-migrate existing JSON data to SQLite on first run."""
    cursor = conn.execute("SELECT COUNT(*) FROM alerts")
    has_alerts = cursor.fetchone()[0] > 0

    # Migrate alerts.json
    alerts_json = _DB_DIR / 'alerts.json'
    if not has_alerts and alerts_json.exists():
        try:
            data = json.loads(alerts_json.read_text(encoding='utf-8'))
            if isinstance(data, list) and data:
                _migrate_alerts(conn, data)
                alerts_json.rename(alerts_json.with_suffix('.json.bak'))
        except Exception:
            pass  # If migration fails, JSON file stays intact

    # Migrate watchlist.json (if it exists)
    wl_json = _DB_DIR / 'watchlist.json'
    if wl_json.exists():
        cursor = conn.execute("SELECT COUNT(*) FROM watchlist")
        if cursor.fetchone()[0] == 0:
            try:
                data = json.loads(wl_json.read_text(encoding='utf-8'))
                if isinstance(data, list) and data:
                    _migrate_watchlist(conn, data)
                    wl_json.rename(wl_json.with_suffix('.json.bak'))
            except Exception:
                pass

    # Migrate scheduler_state.json
    sched_json = _DB_DIR / 'scheduler_state.json'
    if sched_json.exists():
        cursor = conn.execute("SELECT COUNT(*) FROM scheduler_state")
        if cursor.fetchone()[0] == 0:
            try:
                data = json.loads(sched_json.read_text(encoding='utf-8'))
                if isinstance(data, dict) and 'last_run' in data:
                    for market, date_str in data['last_run'].items():
                        conn.execute(
                            "INSERT OR REPLACE INTO scheduler_state (market, last_run) VALUES (?, ?)",
                            (market, date_str)
                        )
                    conn.commit()
                    sched_json.rename(sched_json.with_suffix('.json.bak'))
            except Exception:
                pass


def _migrate_alerts(conn: sqlite3.Connection, alerts_list: list):
    """Bulk insert alerts from JSON list."""
    rows = []
    for a in alerts_list:
        rows.append((
            a.get('symbol', ''),
            a.get('date', ''),
            a.get('direction', ''),
            int(a.get('score', 0)),
            float(a.get('alert_price', 0.0)),
            a.get('criteria', ''),
            a.get('pattern', ''),
            a.get('combo', ''),
            a.get('market', 'us'),
            a.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ))
    conn.executemany(
        """INSERT OR IGNORE INTO alerts
           (symbol, date, direction, score, alert_price, criteria, pattern, combo, market, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows
    )
    conn.commit()


def _migrate_watchlist(conn: sqlite3.Connection, watchlist_list: list):
    """Bulk insert watchlist items from JSON list."""
    rows = []
    for w in watchlist_list:
        rows.append((
            w.get('symbol', ''),
            w.get('date_added', ''),
            w.get('alert_date', w.get('date_added', '')),
            w.get('direction', ''),
            int(w.get('score', 0)),
            float(w.get('alert_price', 0.0)),
            w.get('criteria', ''),
            w.get('pattern', ''),
            w.get('combo', ''),
            w.get('market', 'us'),
            w.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ))
    conn.executemany(
        """INSERT OR IGNORE INTO watchlist
           (symbol, date_added, alert_date, direction, score, alert_price, criteria, pattern, combo, market, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Alerts CRUD
# ---------------------------------------------------------------------------

def db_load_all_alerts() -> List[dict]:
    """Load all alerts from the database."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM alerts ORDER BY date DESC, symbol")
    return [dict(row) for row in cursor.fetchall()]


def db_save_alerts_batch(alerts: List[dict]) -> int:
    """Save multiple alerts. Returns count of new alerts inserted."""
    conn = get_connection()
    rows = []
    for a in alerts:
        rows.append((
            a.get('symbol', ''),
            a.get('date', ''),
            a.get('direction', ''),
            int(a.get('score', 0)),
            float(a.get('alert_price', 0.0)),
            a.get('criteria', ''),
            a.get('pattern', ''),
            a.get('combo', ''),
            a.get('market', 'us'),
            a.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ))

    cursor = conn.executemany(
        """INSERT OR IGNORE INTO alerts
           (symbol, date, direction, score, alert_price, criteria, pattern, combo, market, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows
    )
    conn.commit()
    return cursor.rowcount


def db_get_historical_alerts(days_back: int = 30, market: str = None,
                              direction: str = None) -> List[dict]:
    """Get alerts from the last N days with optional filters."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

    query = "SELECT * FROM alerts WHERE date >= ?"
    params: list = [cutoff]

    if market and market.lower() != 'all':
        query += " AND market = ?"
        params.append(market.lower())

    if direction and direction.lower() != 'all':
        query += " AND direction = ?"
        params.append(direction)

    query += " ORDER BY date DESC, symbol"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def db_get_alerts_by_date(date_str: str, market: str = None) -> List[dict]:
    """Get alerts for a specific date."""
    conn = get_connection()
    if market and market.lower() != 'all':
        cursor = conn.execute(
            "SELECT * FROM alerts WHERE date = ? AND market = ? ORDER BY symbol",
            (date_str, market.lower())
        )
    else:
        cursor = conn.execute(
            "SELECT * FROM alerts WHERE date = ? ORDER BY symbol",
            (date_str,)
        )
    return [dict(row) for row in cursor.fetchall()]


def db_get_alerts_date_range(start_date: str, end_date: str,
                              market: str = None) -> List[dict]:
    """Get alerts within a date range."""
    conn = get_connection()
    if market and market.lower() != 'all':
        cursor = conn.execute(
            "SELECT * FROM alerts WHERE date >= ? AND date <= ? AND market = ? ORDER BY date DESC",
            (start_date, end_date, market.lower())
        )
    else:
        cursor = conn.execute(
            "SELECT * FROM alerts WHERE date >= ? AND date <= ? ORDER BY date DESC",
            (start_date, end_date)
        )
    return [dict(row) for row in cursor.fetchall()]


def db_get_available_dates() -> List[str]:
    """Get list of all dates that have alerts, newest first."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT DISTINCT date FROM alerts ORDER BY date DESC"
    )
    return [row['date'] for row in cursor.fetchall()]


def db_delete_alert(symbol: str, date: str) -> bool:
    """Delete a specific alert. Returns True if deleted."""
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM alerts WHERE symbol = ? AND date = ?",
        (symbol, date)
    )
    conn.commit()
    return cursor.rowcount > 0


def db_clear_old_alerts(days_to_keep: int = 60) -> int:
    """Remove alerts older than N days. Returns count removed."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
    cursor = conn.execute("DELETE FROM alerts WHERE date < ?", (cutoff,))
    conn.commit()
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Watchlist CRUD
# ---------------------------------------------------------------------------

def db_load_watchlist() -> List[dict]:
    """Load all watchlist items."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM watchlist ORDER BY date_added DESC")
    return [dict(row) for row in cursor.fetchall()]


def db_add_watchlist_item(item: dict) -> bool:
    """Add a watchlist item. Returns True if added, False if symbol already exists."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO watchlist
               (symbol, date_added, alert_date, direction, score, alert_price,
                criteria, pattern, combo, market, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.get('symbol', ''),
                item.get('date_added', ''),
                item.get('alert_date', ''),
                item.get('direction', ''),
                int(item.get('score', 0)),
                float(item.get('alert_price', 0.0)),
                item.get('criteria', ''),
                item.get('pattern', ''),
                item.get('combo', ''),
                item.get('market', 'us'),
                item.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            )
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Symbol already in watchlist


def db_remove_watchlist_item(symbol: str) -> bool:
    """Remove a stock from the watchlist. Returns True if removed."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
    conn.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Scheduler state
# ---------------------------------------------------------------------------

def db_get_scheduler_state() -> dict:
    """Get scheduler last_run state as {market: date_str}."""
    conn = get_connection()
    cursor = conn.execute("SELECT market, last_run FROM scheduler_state")
    return {row['market']: row['last_run'] for row in cursor.fetchall()}


def db_set_scheduler_last_run(market: str, date_str: str):
    """Set the last run date for a market."""
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO scheduler_state (market, last_run) VALUES (?, ?)",
        (market, date_str)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Entry Signals CRUD
# ---------------------------------------------------------------------------

def db_save_entry_signals(signals: List[dict]) -> int:
    """Save multiple entry signals. Returns count of new signals inserted.
    Duplicate (symbol, signal_date, direction) are silently skipped."""
    conn = get_connection()
    rows = []
    for s in signals:
        rows.append((
            s.get('symbol', ''),
            s.get('signal_date', ''),
            s.get('direction', ''),
            s.get('strategy', 'Trend Following'),
            s.get('strength', 'Moderate'),
            s.get('setup', ''),
            float(s.get('entry_price', 0)),
            float(s.get('ema20', 0)),
            float(s.get('stop_loss', 0)),
            float(s.get('target_1', 0)),
            float(s.get('target_2', 0)),
            float(s.get('risk_pct', 0)),
            float(s.get('pullback_pct', 0)),
            s.get('adx'),
            s.get('rsi'),
            s.get('volume_ratio'),
            s.get('atr'),
            s.get('conditions_met', ''),
            s.get('conditions_missing', ''),
            s.get('source', 'Watchlist'),
            s.get('market', 'us'),
            s.get('status', 'Active'),
            s.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ))

    cursor = conn.executemany(
        """INSERT OR IGNORE INTO entry_signals
           (symbol, signal_date, direction, strategy, strength, setup,
            entry_price, ema20, stop_loss, target_1, target_2,
            risk_pct, pullback_pct, adx, rsi, volume_ratio, atr,
            conditions_met, conditions_missing,
            source, market, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows
    )
    conn.commit()
    return cursor.rowcount


def db_load_active_entry_signals(source: Optional[str] = None,
                                  market: Optional[str] = None) -> List[dict]:
    """Load entry signals with status='Active', optionally filtered by source/market."""
    conn = get_connection()
    query = "SELECT * FROM entry_signals WHERE status = 'Active'"
    params: list = []

    if source:
        query += " AND source = ?"
        params.append(source)
    if market and market.lower() != 'all':
        query += " AND market = ?"
        params.append(market.lower())

    query += " ORDER BY signal_date DESC, symbol"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def db_load_all_entry_signals(days_back: int = 90) -> List[dict]:
    """Load all entry signals (any status) within date range."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    cursor = conn.execute(
        "SELECT * FROM entry_signals WHERE signal_date >= ? ORDER BY signal_date DESC, symbol",
        (cutoff,)
    )
    return [dict(row) for row in cursor.fetchall()]


def db_update_entry_signal_status(signal_id: int, status: str,
                                   exit_price: float = None,
                                   exit_date: str = None) -> bool:
    """Update the status of an entry signal. Returns True if updated."""
    conn = get_connection()
    if exit_price is not None and exit_date:
        cursor = conn.execute(
            "UPDATE entry_signals SET status = ?, exit_price = ?, exit_date = ? WHERE id = ?",
            (status, exit_price, exit_date, signal_id)
        )
    else:
        cursor = conn.execute(
            "UPDATE entry_signals SET status = ? WHERE id = ?",
            (status, signal_id)
        )
    conn.commit()
    return cursor.rowcount > 0


def db_delete_entry_signal(signal_id: int) -> bool:
    """Delete a specific entry signal. Returns True if deleted."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM entry_signals WHERE id = ?", (signal_id,))
    conn.commit()
    return cursor.rowcount > 0
