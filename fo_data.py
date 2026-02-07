import json
import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

try:
    from jugaad_data.nse import NSELive
    JUGAAD_AVAILABLE = True
except ImportError:
    JUGAAD_AVAILABLE = False

# ---------------------------------------------------------------------------
# Lazy singleton for NSELive (avoids creating session on every import)
# ---------------------------------------------------------------------------
_nse_live_instance: Optional[object] = None


def _get_nse_live():
    """Return a singleton NSELive instance, creating it on first call."""
    global _nse_live_instance
    if _nse_live_instance is None:
        _nse_live_instance = NSELive()
    return _nse_live_instance


# ---------------------------------------------------------------------------
# Local file cache for option chain data
# ---------------------------------------------------------------------------
_CACHE_DIR = Path(__file__).resolve().parent.parent / '.fo_cache'


def _cache_path(symbol: str) -> Path:
    """Return the cache file path for a given symbol."""
    safe_name = symbol.replace('^', '_').replace('.', '_')
    return _CACHE_DIR / f'{safe_name}_option_chain.json'


def _save_to_cache(symbol: str, data: dict) -> None:
    """Save raw option chain dict to local JSON file with a timestamp."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'data': data,
        }
        path = _cache_path(symbol)
        path.write_text(json.dumps(payload, default=str), encoding='utf-8')
    except Exception:
        pass  # caching is best-effort, never block the app


def _load_from_cache(symbol: str) -> Tuple[Optional[dict], Optional[str]]:
    """Load cached option chain data.

    Returns (data_dict, timestamp_str) or (None, None) if no cache exists.
    """
    path = _cache_path(symbol)
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload.get('data'), payload.get('timestamp')
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Symbol helpers
# ---------------------------------------------------------------------------
NSE_SYMBOL_MAP = {
    '^NSEI': 'NIFTY',
    '^NSEBANK': 'BANKNIFTY',
}

INDIAN_INDICES = {'NIFTY', 'BANKNIFTY', 'FINNIFTY'}


def _is_indian_symbol(symbol: str) -> bool:
    """True for any Indian symbol: indices (^NSEI, NIFTY, etc.) or .NS stocks."""
    return (symbol in NSE_SYMBOL_MAP
            or symbol in INDIAN_INDICES
            or symbol.endswith('.NS'))


def _to_nse_symbol(symbol: str) -> str:
    """Convert any incoming symbol to the bare name NSE expects."""
    if symbol in NSE_SYMBOL_MAP:
        return NSE_SYMBOL_MAP[symbol]   # ^NSEI -> NIFTY
    if symbol.endswith('.NS'):
        return symbol[:-3]              # HDFCBANK.NS -> HDFCBANK
    return symbol


def _is_index(symbol: str) -> bool:
    """Check if the symbol is an index (not an equity stock)."""
    nse_sym = _to_nse_symbol(symbol)
    return nse_sym in INDIAN_INDICES


# ---------------------------------------------------------------------------
# jugaad-data wrappers (with local cache fallback)
# ---------------------------------------------------------------------------
def _jugaad_fetch_option_chain(symbol: str) -> Tuple[dict, bool]:
    """Fetch full option chain dict from NSE via jugaad-data.

    Returns (data_dict, is_from_cache).
    - First tries live NSE API.
    - If live data has actual rows, saves to local cache and returns it.
    - If live data is empty (market closed), loads from local cache.
    - Returns ({}, False) if nothing available at all.
    """
    nse = _get_nse_live()
    nse_sym = _to_nse_symbol(symbol)

    # --- Try live fetch ---
    live_data = {}
    try:
        if _is_index(symbol):
            live_data = nse.index_option_chain(nse_sym)
        else:
            live_data = nse.equities_option_chain(nse_sym)
        if not isinstance(live_data, dict):
            live_data = {}
    except Exception:
        live_data = {}

    # Check if live data has actual option chain rows
    records = live_data.get('records', {})
    has_data = bool(records.get('data'))

    if has_data:
        # Live data is good — save to cache and return
        _save_to_cache(symbol, live_data)
        return live_data, False

    # --- Live data empty (market closed) — try local cache ---
    cached_data, cached_ts = _load_from_cache(symbol)
    if cached_data and cached_data.get('records', {}).get('data'):
        return cached_data, True

    return {}, False


def _jugaad_get_expiries(symbol: str) -> Tuple[List[str], bool]:
    """Return (list of expiry-date strings, is_from_cache)."""
    data, from_cache = _jugaad_fetch_option_chain(symbol)
    records = data.get('records', {})
    dates = records.get('expiryDates', [])
    return (dates if isinstance(dates, list) else []), from_cache


def _jugaad_get_chain(
    symbol: str, expiry: str
) -> Tuple[Optional[Tuple[pd.DataFrame, pd.DataFrame]], bool]:
    """Fetch option chain for a specific expiry and return ((calls, puts), is_from_cache).

    Column names are standardised to match yfinance conventions used by the
    rest of the screener: strike, lastPrice, openInterest, impliedVolatility,
    bid, ask, volume.
    """
    data, from_cache = _jugaad_fetch_option_chain(symbol)
    records = data.get('records', {})
    all_rows = records.get('data', [])

    if not all_rows:
        return None, from_cache

    # Filter to the requested expiry
    rows = [r for r in all_rows if r.get('expiryDate') == expiry]
    if not rows:
        return None, from_cache

    # Build calls and puts lists
    call_rows = []
    put_rows = []

    for row in rows:
        strike = row.get('strikePrice', 0)

        ce = row.get('CE')
        if ce and isinstance(ce, dict):
            call_rows.append({
                'strike': float(strike),
                'lastPrice': float(ce.get('lastPrice', 0) or 0),
                'openInterest': float(ce.get('openInterest', 0) or 0),
                'impliedVolatility': float(ce.get('impliedVolatility', 0) or 0) / 100.0,
                'bid': float(ce.get('bidprice', 0) or ce.get('bidPrice', 0) or 0),
                'ask': float(ce.get('askPrice', 0) or 0),
                'volume': float(ce.get('totalTradedVolume', 0) or 0),
            })

        pe = row.get('PE')
        if pe and isinstance(pe, dict):
            put_rows.append({
                'strike': float(strike),
                'lastPrice': float(pe.get('lastPrice', 0) or 0),
                'openInterest': float(pe.get('openInterest', 0) or 0),
                'impliedVolatility': float(pe.get('impliedVolatility', 0) or 0) / 100.0,
                'bid': float(pe.get('bidprice', 0) or pe.get('bidPrice', 0) or 0),
                'ask': float(pe.get('askPrice', 0) or 0),
                'volume': float(pe.get('totalTradedVolume', 0) or 0),
            })

    if not call_rows and not put_rows:
        return None, from_cache

    calls = pd.DataFrame(call_rows) if call_rows else pd.DataFrame(
        columns=['strike', 'lastPrice', 'openInterest', 'impliedVolatility',
                 'bid', 'ask', 'volume'])
    puts = pd.DataFrame(put_rows) if put_rows else pd.DataFrame(
        columns=['strike', 'lastPrice', 'openInterest', 'impliedVolatility',
                 'bid', 'ask', 'volume'])

    return (calls.reset_index(drop=True), puts.reset_index(drop=True)), from_cache


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_expiry_dates(symbol: str) -> Tuple[List[str], bool]:
    """Return (expiry_dates, is_from_cache).

    is_from_cache is True when serving stale data from local disk because the
    market is closed and NSE returns no live data.
    """
    # Try jugaad-data first for Indian symbols
    if JUGAAD_AVAILABLE and _is_indian_symbol(symbol):
        try:
            dates, from_cache = _jugaad_get_expiries(symbol)
            if dates:
                return dates, from_cache
        except Exception:
            pass  # fall through to yfinance

    # yfinance fallback / default for non-Indian symbols
    try:
        ticker = yf.Ticker(symbol)
        return list(ticker.options), False
    except Exception:
        return [], False


@st.cache_data(ttl=300, show_spinner=False)
def get_option_chain(
    symbol: str, expiry: str
) -> Tuple[Optional[Tuple[pd.DataFrame, pd.DataFrame]], bool]:
    """Return ((calls_df, puts_df), is_from_cache) or (None, False)."""
    # Try jugaad-data first for Indian symbols
    if JUGAAD_AVAILABLE and _is_indian_symbol(symbol):
        try:
            result, from_cache = _jugaad_get_chain(symbol, expiry)
            if result is not None:
                return result, from_cache
        except Exception:
            pass  # fall through to yfinance

    # yfinance fallback / default
    try:
        ticker = yf.Ticker(symbol)
        chain = ticker.option_chain(expiry)
        # Normalize yfinance column names to match our standard
        calls = _normalize_yf_chain(chain.calls)
        puts = _normalize_yf_chain(chain.puts)
        return (calls, puts), False
    except Exception:
        return None, False


def _normalize_yf_chain(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance option chain columns to standard format."""
    if df.empty:
        return pd.DataFrame(columns=['strike', 'lastPrice', 'openInterest',
                                     'impliedVolatility', 'bid', 'ask', 'volume'])

    # yfinance column mapping
    col_map = {
        'strike': 'strike',
        'lastPrice': 'lastPrice',
        'openInterest': 'openInterest',
        'impliedVolatility': 'impliedVolatility',
        'bid': 'bid',
        'ask': 'ask',
        'volume': 'volume',
    }

    result = pd.DataFrame()
    for std_col, yf_col in col_map.items():
        if yf_col in df.columns:
            result[std_col] = df[yf_col]
        else:
            result[std_col] = 0

    return result.reset_index(drop=True)


def get_cache_timestamp(symbol: str) -> Optional[str]:
    """Return the ISO timestamp of the cached data for a symbol, or None."""
    _, ts = _load_from_cache(symbol)
    return ts


def compute_pcr(calls: pd.DataFrame, puts: pd.DataFrame) -> dict:
    total_call_oi = calls['openInterest'].fillna(0).sum()
    total_put_oi = puts['openInterest'].fillna(0).sum()
    total_call_vol = calls['volume'].fillna(0).sum()
    total_put_vol = puts['volume'].fillna(0).sum()

    pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
    pcr_vol = total_put_vol / total_call_vol if total_call_vol > 0 else 0

    return {
        'PCR (OI)': round(float(pcr_oi), 3),
        'PCR (Volume)': round(float(pcr_vol), 3),
        'Total Call OI': int(total_call_oi),
        'Total Put OI': int(total_put_oi),
        'Total Call Volume': int(total_call_vol),
        'Total Put Volume': int(total_put_vol),
    }


def compute_max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float:
    all_strikes = sorted(set(
        calls['strike'].tolist() + puts['strike'].tolist()
    ))
    if not all_strikes:
        return 0.0

    min_pain = float('inf')
    max_pain_strike = all_strikes[0]

    for strike in all_strikes:
        # Call writers pay when price > strike
        call_pain = calls.apply(
            lambda r: max(0, strike - r['strike']) * r.get('openInterest', 0)
            if pd.notna(r.get('openInterest')) else 0, axis=1
        ).sum()
        # Put writers pay when price < strike
        put_pain = puts.apply(
            lambda r: max(0, r['strike'] - strike) * r.get('openInterest', 0)
            if pd.notna(r.get('openInterest')) else 0, axis=1
        ).sum()
        total_pain = call_pain + put_pain
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = strike

    return float(max_pain_strike)


def oi_analysis(calls: pd.DataFrame, puts: pd.DataFrame, current_price: float) -> dict:
    max_pain = compute_max_pain(calls, puts)

    highest_call_oi = 0.0
    highest_put_oi = 0.0
    if not calls.empty and calls['openInterest'].notna().any():
        highest_call_oi = float(calls.loc[calls['openInterest'].idxmax(), 'strike'])
    if not puts.empty and puts['openInterest'].notna().any():
        highest_put_oi = float(puts.loc[puts['openInterest'].idxmax(), 'strike'])

    return {
        'Max Pain': max_pain,
        'Highest Call OI Strike': highest_call_oi,
        'Highest Put OI Strike': highest_put_oi,
        'Current Price': current_price,
    }


def get_option_flow_summary(
    symbol: str,
    current_price: float,
    direction: str = 'Bullish',
) -> Optional[dict]:
    """Get option flow summary for a stock to help decide if options are worth buying.

    Returns a dict with:
    - expiry: nearest expiry date
    - pcr: put-call ratio (OI based)
    - oi_bias: 'Bullish'/'Bearish'/'Neutral' based on PCR
    - top_strikes: list of best strikes to consider (based on direction)
    - max_pain: max pain strike
    - recommendation: brief buy/avoid recommendation
    """
    try:
        expiries, from_cache = get_expiry_dates(symbol)
        if not expiries:
            return None

        # Use weekly/monthly expiry for better OI data (skip 0-2 day expiries)
        # For US stocks, prefer 1-2 week out expiry for better liquidity
        from datetime import datetime, timedelta
        today = datetime.now().date()
        nearest_expiry = expiries[0]

        # Find an expiry that's at least 5 days out for better OI data
        for exp in expiries:
            try:
                exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
                if (exp_date - today).days >= 5:
                    nearest_expiry = exp
                    break
            except ValueError:
                continue

        chain_result, _ = get_option_chain(symbol, nearest_expiry)
        if chain_result is None:
            return None

        calls, puts = chain_result

        # Compute PCR
        pcr_data = compute_pcr(calls, puts)
        pcr_oi = pcr_data['PCR (OI)']

        # Determine OI bias
        if pcr_oi > 1.2:
            oi_bias = 'Bullish'  # Heavy put writing = support
        elif pcr_oi < 0.8:
            oi_bias = 'Bearish'  # Heavy call writing = resistance
        else:
            oi_bias = 'Neutral'

        # Get max pain and key levels
        max_pain = compute_max_pain(calls, puts)
        oi_data = oi_analysis(calls, puts, current_price)

        # Find top strikes based on direction
        top_strikes = []

        # Check if we have OI data (yfinance often returns 0 for OI)
        total_oi = calls['openInterest'].fillna(0).sum() + puts['openInterest'].fillna(0).sum()
        use_volume_scoring = total_oi == 0  # Fallback to volume if no OI data

        if direction == 'Bullish':
            # For bullish: look for ATM/slightly OTM calls with good OI and volume
            atm_calls = calls[
                (calls['strike'] >= current_price * 0.97) &
                (calls['strike'] <= current_price * 1.05)
            ].copy()
            if not atm_calls.empty:
                if use_volume_scoring:
                    # Use volume only when OI is not available
                    atm_calls['score'] = atm_calls['volume'].fillna(0)
                else:
                    atm_calls['score'] = (
                        atm_calls['openInterest'].fillna(0) * 0.6 +
                        atm_calls['volume'].fillna(0) * 0.4
                    )
                top_calls = atm_calls.nlargest(3, 'score')
                for _, row in top_calls.iterrows():
                    iv_pct = row.get('impliedVolatility', 0)
                    if isinstance(iv_pct, (int, float)):
                        iv_display = f"{iv_pct * 100:.1f}%" if iv_pct < 1 else f"{iv_pct:.1f}%"
                    else:
                        iv_display = "N/A"
                    top_strikes.append({
                        'strike': float(row['strike']),
                        'type': 'CALL',
                        'ltp': float(row.get('lastPrice', 0) or 0),
                        'oi': int(row.get('openInterest', 0) or 0),
                        'volume': int(row.get('volume', 0) or 0),
                        'iv': iv_display,
                    })
        else:
            # For bearish: look for ATM/slightly OTM puts with good OI and volume
            atm_puts = puts[
                (puts['strike'] >= current_price * 0.95) &
                (puts['strike'] <= current_price * 1.03)
            ].copy()
            if not atm_puts.empty:
                if use_volume_scoring:
                    atm_puts['score'] = atm_puts['volume'].fillna(0)
                else:
                    atm_puts['score'] = (
                        atm_puts['openInterest'].fillna(0) * 0.6 +
                        atm_puts['volume'].fillna(0) * 0.4
                    )
                top_puts = atm_puts.nlargest(3, 'score')
                for _, row in top_puts.iterrows():
                    iv_pct = row.get('impliedVolatility', 0)
                    if isinstance(iv_pct, (int, float)):
                        iv_display = f"{iv_pct * 100:.1f}%" if iv_pct < 1 else f"{iv_pct:.1f}%"
                    else:
                        iv_display = "N/A"
                    top_strikes.append({
                        'strike': float(row['strike']),
                        'type': 'PUT',
                        'ltp': float(row.get('lastPrice', 0) or 0),
                        'oi': int(row.get('openInterest', 0) or 0),
                        'volume': int(row.get('volume', 0) or 0),
                        'iv': iv_display,
                    })

        # Generate recommendation
        recommendation = _generate_option_recommendation(
            direction, oi_bias, pcr_oi, current_price, max_pain, top_strikes,
            use_volume_scoring
        )

        return {
            'expiry': nearest_expiry,
            'pcr_oi': round(pcr_oi, 3),
            'pcr_vol': round(pcr_data['PCR (Volume)'], 3),
            'oi_bias': oi_bias,
            'max_pain': max_pain,
            'highest_call_oi': oi_data['Highest Call OI Strike'],
            'highest_put_oi': oi_data['Highest Put OI Strike'],
            'top_strikes': top_strikes,
            'recommendation': recommendation,
            'from_cache': from_cache,
            'total_call_oi': pcr_data['Total Call OI'],
            'total_put_oi': pcr_data['Total Put OI'],
            'volume_based': use_volume_scoring,  # Flag to indicate OI data was not available
        }

    except Exception:
        return None


def _generate_option_recommendation(
    direction: str,
    oi_bias: str,
    pcr_oi: float,
    current_price: float,
    max_pain: float,
    top_strikes: List[dict],
    volume_based: bool = False,
) -> dict:
    """Generate a recommendation on whether to buy options."""
    reasons = []
    score = 0  # -2 to +2 scale

    # If using volume-based analysis (no OI data), note it
    if volume_based:
        reasons.append("OI data unavailable - using volume for analysis")

    # Check if direction aligns with OI bias (skip if no OI data)
    if not volume_based:
        if direction == 'Bullish' and oi_bias == 'Bullish':
            score += 1
            reasons.append("PCR supports bullish view (put writing = support)")
        elif direction == 'Bearish' and oi_bias == 'Bearish':
            score += 1
            reasons.append("PCR supports bearish view (call writing = resistance)")
        elif oi_bias == 'Neutral':
            reasons.append("PCR is neutral - no strong directional bias from OI")
        else:
            score -= 1
            reasons.append(f"PCR ({pcr_oi:.2f}) contradicts {direction.lower()} view")

        # Check distance from max pain (only meaningful with OI data)
        if max_pain > 0:
            distance_pct = abs(current_price - max_pain) / max_pain * 100
            if distance_pct < 2:
                score += 1
                reasons.append(f"Price near Max Pain ({max_pain:.0f}) - may stay range-bound")
            elif distance_pct > 5:
                if (direction == 'Bullish' and current_price > max_pain) or \
                   (direction == 'Bearish' and current_price < max_pain):
                    score += 1
                    reasons.append(f"Price has momentum away from Max Pain ({max_pain:.0f})")
                else:
                    reasons.append(f"Price may revert toward Max Pain ({max_pain:.0f})")

    # Check if we have liquid strikes
    if top_strikes:
        avg_vol = sum(s['volume'] for s in top_strikes) / len(top_strikes)
        if volume_based:
            # Volume-based liquidity check
            if avg_vol > 5000:
                score += 1
                reasons.append(f"High volume ({avg_vol:.0f} avg) - good liquidity")
            elif avg_vol > 1000:
                reasons.append(f"Moderate volume ({avg_vol:.0f} avg)")
            else:
                score -= 1
                reasons.append(f"Low volume ({avg_vol:.0f} avg) - liquidity concern")
        else:
            # OI-based liquidity check
            avg_oi = sum(s['oi'] for s in top_strikes) / len(top_strikes)
            if avg_oi > 10000 and avg_vol > 1000:
                score += 1
                reasons.append("Good liquidity in suggested strikes")
            elif avg_oi < 1000:
                score -= 1
                reasons.append("Low OI - may face liquidity issues")
    else:
        score -= 1
        reasons.append("No suitable strikes found near current price")

    # Final verdict
    if score >= 2:
        verdict = "FAVORABLE"
        action = "Consider buying options"
    elif score >= 0:
        verdict = "MODERATE"
        action = "Proceed with caution, use tight stop-loss"
    else:
        verdict = "AVOID"
        action = "Option flow doesn't support this trade"

    return {
        'verdict': verdict,
        'action': action,
        'reasons': reasons,
        'score': score,
    }
