import pandas as pd
import yfinance as yf
import streamlit as st
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from screener.config import CACHE_TTL_SECONDS

# Local cache directory
_CACHE_DIR = Path(__file__).resolve().parent.parent / '.data_cache'
_CACHE_META_FILE = _CACHE_DIR / 'cache_meta.json'


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_cache_path(market: str, interval: str) -> Path:
    """Get cache file path for a market/interval combination."""
    return _CACHE_DIR / f'{market}_{interval}_data.pkl'


def _load_cache_meta() -> dict:
    """Load cache metadata."""
    if not _CACHE_META_FILE.exists():
        return {}
    try:
        return json.loads(_CACHE_META_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_cache_meta(meta: dict):
    """Save cache metadata."""
    _ensure_cache_dir()
    _CACHE_META_FILE.write_text(json.dumps(meta, indent=2), encoding='utf-8')


def get_cache_info(market: str, interval: str = '1d') -> dict:
    """Get cache info for a market."""
    meta = _load_cache_meta()
    key = f'{market}_{interval}'
    if key in meta:
        return {
            'cached': True,
            'last_updated': meta[key].get('last_updated', 'Unknown'),
            'stock_count': meta[key].get('stock_count', 0),
        }
    return {'cached': False, 'last_updated': None, 'stock_count': 0}


def load_cached_data(market: str, interval: str = '1d') -> Optional[Dict[str, pd.DataFrame]]:
    """Load data from local cache if available."""
    cache_path = _get_cache_path(market, interval)
    if not cache_path.exists():
        return None

    try:
        data = pd.read_pickle(cache_path)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_to_cache(data: Dict[str, pd.DataFrame], market: str, interval: str = '1d'):
    """Save data to local cache."""
    _ensure_cache_dir()
    cache_path = _get_cache_path(market, interval)

    try:
        pd.to_pickle(data, cache_path)

        # Update metadata
        meta = _load_cache_meta()
        key = f'{market}_{interval}'
        meta[key] = {
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stock_count': len(data),
        }
        _save_cache_meta(meta)
    except Exception:
        pass


def clear_cache(market: str = None, interval: str = '1d'):
    """Clear cache for a specific market or all caches."""
    if market:
        cache_path = _get_cache_path(market, interval)
        if cache_path.exists():
            cache_path.unlink()
        meta = _load_cache_meta()
        key = f'{market}_{interval}'
        if key in meta:
            del meta[key]
            _save_cache_meta(meta)
    else:
        # Clear all caches
        if _CACHE_DIR.exists():
            for f in _CACHE_DIR.glob('*.pkl'):
                f.unlink()
        _save_cache_meta({})


def _days_to_period(days: int) -> str:
    if days <= 7:
        return '5d'
    elif days <= 30:
        return '1mo'
    elif days <= 90:
        return '3mo'
    elif days <= 180:
        return '6mo'
    elif days <= 365:
        return '1y'
    elif days <= 730:
        return '2y'
    else:
        return '5y'


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns from yfinance 1.x output."""
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance 1.x single ticker: ('Close', 'AAPL') -> take level 0
        # yfinance 1.x batch group_by=ticker: ('AAPL', 'Close') -> handled separately
        df.columns = df.columns.get_level_values(0)
    # Standardize column names
    col_map = {c: c.capitalize() for c in df.columns}
    df = df.rename(columns=col_map)
    return df


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_ohlcv(symbol: str, period_days: int = 365,
                interval: str = '1d') -> Optional[pd.DataFrame]:
    try:
        period = _days_to_period(period_days)
        df = yf.download(symbol, period=period, interval=interval,
                         auto_adjust=True, progress=False)
        if df.empty:
            return None
        df = _flatten_columns(df)
        df = df.dropna(how='all')
        # Ensure required columns exist
        required = {'Open', 'High', 'Low', 'Close', 'Volume'}
        if not required.issubset(set(df.columns)):
            return None
        return df
    except Exception:
        return None


def fetch_batch_fresh(symbols: list, period_days: int = 365,
                      interval: str = '1d', market: str = 'us') -> Dict[str, pd.DataFrame]:
    """Fetch fresh data from Yahoo Finance (bypasses cache)."""
    result = {}
    period = _days_to_period(period_days)

    chunk_size = 20
    total = len(symbols)
    progress = st.progress(0, text="Downloading fresh data...")

    for i in range(0, total, chunk_size):
        chunk = symbols[i:i + chunk_size]
        pct = min(i / total, 0.99)
        progress.progress(pct, text=f"Downloading {i}/{total} stocks...")

        try:
            if len(chunk) == 1:
                df = fetch_ohlcv(chunk[0], period_days, interval)
                if df is not None and len(df) > 20:
                    result[chunk[0]] = df
                continue

            tickers_str = " ".join(chunk)
            raw = yf.download(tickers_str, period=period, interval=interval,
                              auto_adjust=True, progress=False,
                              group_by='ticker', threads=True)

            if raw.empty:
                for sym in chunk:
                    df = fetch_ohlcv(sym, period_days, interval)
                    if df is not None and len(df) > 20:
                        result[sym] = df
                continue

            for sym in chunk:
                try:
                    # yfinance 1.x batch: columns are (Ticker, Price) MultiIndex
                    if isinstance(raw.columns, pd.MultiIndex):
                        df = raw[sym].copy()
                    else:
                        df = raw.copy()

                    # Flatten any remaining MultiIndex
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(-1)

                    df = df.dropna(how='all')
                    col_map = {c: c.capitalize() for c in df.columns}
                    df = df.rename(columns=col_map)

                    required = {'Open', 'High', 'Low', 'Close', 'Volume'}
                    if not required.issubset(set(df.columns)):
                        continue

                    if not df.empty and len(df) > 20:
                        result[sym] = df
                except (KeyError, Exception):
                    try:
                        df = fetch_ohlcv(sym, period_days, interval)
                        if df is not None and len(df) > 20:
                            result[sym] = df
                    except Exception:
                        pass

        except Exception:
            for sym in chunk:
                try:
                    df = fetch_ohlcv(sym, period_days, interval)
                    if df is not None and len(df) > 20:
                        result[sym] = df
                except Exception:
                    pass

    progress.progress(1.0, text=f"Done! Loaded {len(result)}/{total} stocks")

    # Save to local cache
    save_to_cache(result, market, interval)

    return result


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Fetching market data...")
def fetch_batch(symbols: list, period_days: int = 365,
                interval: str = '1d') -> Dict[str, pd.DataFrame]:
    """Fetch batch data with Streamlit's session cache."""
    result = {}
    period = _days_to_period(period_days)

    chunk_size = 20
    total = len(symbols)
    progress = st.progress(0, text="Downloading...")

    for i in range(0, total, chunk_size):
        chunk = symbols[i:i + chunk_size]
        pct = min(i / total, 0.99)
        progress.progress(pct, text=f"Downloading {i}/{total} stocks...")

        try:
            if len(chunk) == 1:
                df = fetch_ohlcv(chunk[0], period_days, interval)
                if df is not None and len(df) > 20:
                    result[chunk[0]] = df
                continue

            tickers_str = " ".join(chunk)
            raw = yf.download(tickers_str, period=period, interval=interval,
                              auto_adjust=True, progress=False,
                              group_by='ticker', threads=True)

            if raw.empty:
                for sym in chunk:
                    df = fetch_ohlcv(sym, period_days, interval)
                    if df is not None and len(df) > 20:
                        result[sym] = df
                continue

            for sym in chunk:
                try:
                    # yfinance 1.x batch: columns are (Ticker, Price) MultiIndex
                    if isinstance(raw.columns, pd.MultiIndex):
                        df = raw[sym].copy()
                    else:
                        df = raw.copy()

                    # Flatten any remaining MultiIndex
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(-1)

                    df = df.dropna(how='all')
                    col_map = {c: c.capitalize() for c in df.columns}
                    df = df.rename(columns=col_map)

                    required = {'Open', 'High', 'Low', 'Close', 'Volume'}
                    if not required.issubset(set(df.columns)):
                        continue

                    if not df.empty and len(df) > 20:
                        result[sym] = df
                except (KeyError, Exception):
                    try:
                        df = fetch_ohlcv(sym, period_days, interval)
                        if df is not None and len(df) > 20:
                            result[sym] = df
                    except Exception:
                        pass

        except Exception:
            for sym in chunk:
                try:
                    df = fetch_ohlcv(sym, period_days, interval)
                    if df is not None and len(df) > 20:
                        result[sym] = df
                except Exception:
                    pass

    progress.progress(1.0, text=f"Done! Loaded {len(result)}/{total} stocks")
    return result


def fetch_weekly(symbol: str) -> Optional[pd.DataFrame]:
    return fetch_ohlcv(symbol, period_days=730, interval='1wk')
