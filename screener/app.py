import sys
from pathlib import Path

# Add project root to path so screener package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

st.set_page_config(
    page_title="Daily Trading Screener",
    page_icon="\U0001F4C8",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from screener.stock_lists import get_stock_list
from screener.data_fetcher import (
    fetch_batch,
    fetch_batch_fresh,
    load_cached_data,
    save_to_cache,
    get_cache_info,
    clear_cache,
)
from screener.config import DEFAULT_LOOKBACK_DAYS, WEEKLY_LOOKBACK_DAYS

# --- Sidebar ---
st.sidebar.title("Daily Trading Screener")

market = st.sidebar.radio("Market", ["US", "Indian"])
if market == "Indian":
    index = st.sidebar.selectbox("Index", ["Nifty 50", "Nifty 200", "BankNifty"])
else:
    index = "S&P 500"

timeframe = st.sidebar.radio("Timeframe", ["Daily", "Weekly", "Both"])
custom_tickers = st.sidebar.text_area("Custom Tickers (comma-separated)", "",
                                       help="Override index selection with custom tickers")

# Build ticker list
index_key = index.lower().replace(" ", "").replace("&", "")
symbols, index_symbol = get_stock_list(market.lower(), index_key)

if custom_tickers.strip():
    suffix = ".NS" if market == "Indian" else ""
    symbols = [t.strip().upper() + suffix for t in custom_tickers.split(",") if t.strip()]

st.sidebar.markdown(f"**Scanning {len(symbols)} stocks**")

# --- Data Loading with Cache ---
st.sidebar.markdown("---")
st.sidebar.markdown("### Data Status")

# Get cache info
market_key = market.lower()
cache_info = get_cache_info(market_key, '1d')

# Initialize session state for force refresh
if 'force_refresh' not in st.session_state:
    st.session_state.force_refresh = False

# Show cache status
if cache_info['cached'] and not st.session_state.force_refresh:
    st.sidebar.success(f"📦 Using cached data")
    st.sidebar.caption(f"Last updated: {cache_info['last_updated']}")
    st.sidebar.caption(f"Stocks: {cache_info['stock_count']}")
else:
    st.sidebar.info("🔄 Will fetch fresh data")

# Refresh button
col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("🔄 Refresh Data", help="Fetch fresh data from Yahoo Finance"):
        st.session_state.force_refresh = True
        clear_cache(market_key, '1d')
        if timeframe in ("Weekly", "Both"):
            clear_cache(market_key, '1wk')
        st.rerun()

with col2:
    if st.button("🗑️ Clear Cache", help="Clear all cached data"):
        clear_cache()
        st.session_state.force_refresh = True
        st.rerun()

# --- Fetch Data ---
daily_data = {}
weekly_data = {}

if symbols:
    # Check if we should use cached data
    use_cache = cache_info['cached'] and not st.session_state.force_refresh and not custom_tickers.strip()

    if use_cache:
        # Try to load from local cache
        daily_data = load_cached_data(market_key, '1d')
        if daily_data:
            st.sidebar.success(f"Daily: {len(daily_data)} stocks (cached)")
        else:
            # Cache miss - fetch fresh
            daily_data = fetch_batch_fresh(symbols, period_days=DEFAULT_LOOKBACK_DAYS, interval='1d', market=market_key)
            st.sidebar.success(f"Daily: {len(daily_data)} / {len(symbols)} loaded")
    else:
        # Fetch fresh data
        daily_data = fetch_batch_fresh(symbols, period_days=DEFAULT_LOOKBACK_DAYS, interval='1d', market=market_key)
        st.sidebar.success(f"Daily: {len(daily_data)} / {len(symbols)} loaded")
        # Reset force refresh flag
        st.session_state.force_refresh = False

    if timeframe in ("Weekly", "Both"):
        weekly_cache_info = get_cache_info(market_key, '1wk')
        use_weekly_cache = weekly_cache_info['cached'] and not st.session_state.force_refresh and not custom_tickers.strip()

        if use_weekly_cache:
            weekly_data = load_cached_data(market_key, '1wk')
            if weekly_data:
                st.sidebar.success(f"Weekly: {len(weekly_data)} stocks (cached)")
            else:
                weekly_data = fetch_batch_fresh(symbols, period_days=WEEKLY_LOOKBACK_DAYS, interval='1wk', market=market_key)
                st.sidebar.success(f"Weekly: {len(weekly_data)} / {len(symbols)} loaded")
        else:
            weekly_data = fetch_batch_fresh(symbols, period_days=WEEKLY_LOOKBACK_DAYS, interval='1wk', market=market_key)
            st.sidebar.success(f"Weekly: {len(weekly_data)} / {len(symbols)} loaded")

if not daily_data:
    st.warning("No data loaded. Check your internet connection or try different tickers.")
    st.stop()

# --- Market Mood Panel (above tabs) ---
from screener.pages.page_mood import render_mood_panel
render_mood_panel(daily_data, market.lower(), index_symbol)

# --- Tabs ---
(tab_alerts, tab_scanner, tab_technicals, tab_breakouts,
 tab_sr, tab_fo, tab_signals, tab_chart, tab_backtest, tab_tracker, tab_watchlist, tab_guide) = st.tabs([
    "🔔 Alerts",
    "🕯️ Scanner",
    "📐 Technicals",
    "🚀 Breakouts",
    "📍 S/R Levels",
    "📊 F&O Data",
    "💡 Trade Signals",
    "📈 Chart",
    "🧪 Backtest",
    "🗂️ Tracker",
    "⭐ Watchlist",
    "📚 Guide",
])

with tab_alerts:
    from screener.pages.page_alerts import render as render_alerts
    render_alerts(daily_data, weekly_data, market.lower(), index_symbol)

with tab_scanner:
    from screener.pages.page_scanner import render as render_scanner
    render_scanner(daily_data)

with tab_technicals:
    from screener.pages.page_technicals import render as render_technicals
    render_technicals(daily_data)

with tab_breakouts:
    from screener.pages.page_breakouts import render as render_breakouts
    render_breakouts(daily_data)

with tab_sr:
    from screener.pages.page_sr_levels import render as render_sr
    render_sr(daily_data)

with tab_fo:
    from screener.pages.page_fo import render as render_fo
    render_fo(daily_data)

with tab_signals:
    from screener.pages.page_signals import render as render_signals
    render_signals(daily_data, market.lower(), index_symbol)

with tab_chart:
    from screener.pages.page_chart import render as render_chart
    render_chart(daily_data, weekly_data)

with tab_backtest:
    from screener.pages.page_backtest import render as render_backtest
    render_backtest(daily_data)

with tab_tracker:
    from screener.pages.page_tracker import render as render_tracker
    render_tracker(daily_data, market.lower())

with tab_watchlist:
    from screener.pages.page_watchlist import render as render_watchlist
    render_watchlist(daily_data, market.lower())

with tab_guide:
    from screener.pages.page_guide import render as render_guide
    render_guide()
