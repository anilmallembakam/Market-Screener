"""Watchlist Monitor page - Track curated stocks with full performance data."""
import streamlit as st
import pandas as pd
import yfinance as yf
from typing import Dict, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from screener.watchlist_store import load_watchlist, remove_from_watchlist
from screener.alert_history import fetch_performance_data, calculate_performance
from screener.utils import get_chart_url


@st.cache_data(ttl=300, show_spinner=False)
def _cached_fetch_watchlist_perf(symbol: str, date_added: str):
    """Fetch performance data from date added until now."""
    days_since = (datetime.now() - datetime.strptime(date_added, '%Y-%m-%d')).days
    track_days = max(days_since + 5, 10)  # Extra buffer for weekends
    return fetch_performance_data(symbol, date_added, track_days)


@st.cache_data(ttl=3600, show_spinner=False)
def _get_earnings_date(symbol: str) -> str:
    """Get next earnings date for a symbol."""
    try:
        ticker = yf.Ticker(symbol)
        calendar = ticker.calendar

        if calendar is None or calendar.empty:
            return ""

        if 'Earnings Date' in calendar.index:
            earnings_date = calendar.loc['Earnings Date']
            if isinstance(earnings_date, pd.Series):
                earnings_date = earnings_date.iloc[0]
        elif hasattr(calendar, 'columns') and len(calendar.columns) > 0:
            earnings_date = calendar.columns[0]
        else:
            return ""

        if pd.isna(earnings_date):
            return ""

        if isinstance(earnings_date, str):
            earnings_date = pd.to_datetime(earnings_date)
        elif hasattr(earnings_date, 'to_pydatetime'):
            earnings_date = earnings_date.to_pydatetime()

        today = datetime.now()
        if hasattr(earnings_date, 'tzinfo') and earnings_date.tzinfo is not None:
            earnings_date = earnings_date.replace(tzinfo=None)

        days_until = (earnings_date - today).days

        if -7 <= days_until <= 7:
            if days_until < 0:
                return f"📅 {days_until}d"
            elif days_until == 0:
                return "📅 Today!"
            else:
                return f"📅 {days_until}d"
        return ""
    except Exception:
        return ""


def _safe_market(val) -> str:
    """Safely get market value as uppercase string."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 'US'
    return str(val).upper()


def _process_single_watchlist_item(item: dict) -> dict:
    """Process a single watchlist item: fetch performance, earnings, chart URL."""
    symbol = item['symbol']
    date_added = item.get('date_added', datetime.now().strftime('%Y-%m-%d'))
    item_market = _safe_market(item.get('market', 'us'))

    price_data = _cached_fetch_watchlist_perf(symbol, date_added)
    perf = calculate_performance(item, price_data)
    earnings_info = _get_earnings_date(symbol)
    chart_url = get_chart_url(symbol)

    display_symbol = symbol.replace('.NS', '') if symbol.endswith('.NS') else symbol
    days_in_watchlist = (datetime.now() - datetime.strptime(date_added, '%Y-%m-%d')).days

    return {
        'Symbol': display_symbol,
        '_raw_symbol': symbol,  # Keep raw for removal
        'Chart': chart_url,
        'Market': item_market,
        'Date Added': date_added,
        'Days': days_in_watchlist,
        'Direction': item.get('direction', 'N/A'),
        'Score': item.get('score', 0),
        'Setup': item.get('combo', 'N/A'),
        'Criteria': item.get('criteria', ''),
        'Earnings': earnings_info,
        'Alert $': item.get('alert_price', 0),
        'Now $': perf['current_price'],
        'P&L %': perf['pnl_pct'],
        'Max Gain %': perf['max_gain_pct'],
        'Max DD %': perf['max_drawdown_pct'],
        'Status': perf['status'],
        'Momentum': perf['momentum'],
        'Notes': item.get('notes', ''),
    }


def _process_watchlist_parallel(watchlist: List[dict], progress_bar=None) -> List[dict]:
    """Process all watchlist items in parallel."""
    total = len(watchlist)
    results = [None] * total

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_idx = {}
        for idx, item in enumerate(watchlist):
            future = executor.submit(_process_single_watchlist_item, item)
            future_to_idx[future] = idx

        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                pass
            completed += 1
            if progress_bar:
                progress_bar.progress(completed / total, text=f"Processing {completed}/{total}...")

    return [r for r in results if r is not None]


def _render_summary_metrics(perf_df: pd.DataFrame):
    """Render summary metrics row."""
    col1, col2, col3, col4, col5 = st.columns(5)

    total = len(perf_df)
    winners = len(perf_df[perf_df['P&L %'] >= 5])
    losers = len(perf_df[perf_df['P&L %'] <= -5])
    avg_pnl = perf_df['P&L %'].mean()
    losing_steam = len(perf_df[perf_df['Momentum'] == 'Losing Steam'])

    with col1:
        st.metric("Total Stocks", total)
    with col2:
        st.metric("Winners (>5%)", winners,
                  delta=f"{winners/total*100:.0f}%" if total else None)
    with col3:
        st.metric("Losers (<-5%)", losers,
                  delta=f"-{losers/total*100:.0f}%" if total else None,
                  delta_color="inverse")
    with col4:
        st.metric("Avg P&L", f"{avg_pnl:.1f}%",
                  delta="Good" if avg_pnl > 0 else "Bad")
    with col5:
        st.metric("Losing Steam", losing_steam,
                  delta="Watch" if losing_steam > 0 else None,
                  delta_color="off")


def _render_performance_table(perf_df: pd.DataFrame):
    """Render styled performance dataframe."""
    def color_pnl(val):
        if val >= 5:
            return 'background-color: #1b5e20; color: white'
        elif val >= 0:
            return 'background-color: #2e7d32; color: white'
        elif val >= -5:
            return 'background-color: #ff8f00; color: black'
        else:
            return 'background-color: #b71c1c; color: white'

    def color_momentum(val):
        if val == 'Strong':
            return 'background-color: #1b5e20; color: white'
        elif val == 'Stable':
            return 'background-color: #2e7d32; color: white'
        elif val == 'Slowing':
            return 'background-color: #ff8f00; color: black'
        elif val == 'Losing Steam':
            return 'background-color: #b71c1c; color: white'
        return ''

    display_cols = [
        'Symbol', 'Chart', 'Market', 'Date Added', 'Days',
        'Direction', 'Score', 'Setup', 'Criteria', 'Earnings',
        'Alert $', 'Now $', 'P&L %', 'Max Gain %', 'Max DD %',
        'Status', 'Momentum', 'Notes'
    ]
    display_df = perf_df[[c for c in display_cols if c in perf_df.columns]]

    st.dataframe(
        display_df.style
            .applymap(color_pnl, subset=['P&L %'])
            .applymap(color_momentum, subset=['Momentum']),
        use_container_width=True,
        hide_index=True,
        column_config={
            'Symbol': st.column_config.TextColumn('Symbol', width='small'),
            'Chart': st.column_config.LinkColumn('📈', display_text='📈', width='small'),
            'Earnings': st.column_config.TextColumn('Earn', width='small'),
            'Alert $': st.column_config.NumberColumn('Alert $', format="%.2f"),
            'Now $': st.column_config.NumberColumn('Now $', format="%.2f"),
            'P&L %': st.column_config.NumberColumn('P&L %', format="%.1f%%"),
            'Max Gain %': st.column_config.NumberColumn('Max %', format="%.1f%%"),
            'Max DD %': st.column_config.NumberColumn('DD %', format="%.1f%%"),
        }
    )


def render(daily_data: Dict[str, pd.DataFrame], market: str = 'us'):
    watchlist = load_watchlist()

    st.header(f"Watchlist Monitor ({len(watchlist)} stocks)")

    if not watchlist:
        st.info("Your watchlist is empty. Add stocks from the **Alerts/Summary** tab.")
        st.markdown("""
        **How it works:**
        1. Go to the **Alerts/Summary** tab
        2. Open a stock's detail view and click **Add to Watchlist**
        3. Or use the bulk **Add Selected to Watchlist** above the detail view
        4. Come back here to monitor their performance
        """)
        return

    # Controls row
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        market_filter = st.selectbox(
            "Market",
            ['All', 'US', 'Indian'],
            index=0,
            key='wl_market'
        )
    with col2:
        direction_filter = st.selectbox(
            "Direction",
            ['All', 'Bullish', 'Bearish'],
            index=0,
            key='wl_direction'
        )
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            ['Date Added', 'Score', 'P&L %', 'Symbol'],
            index=0,
            key='wl_sort'
        )

    # Apply pre-filters to watchlist before fetching performance
    filtered_watchlist = watchlist
    if market_filter != 'All':
        filtered_watchlist = [
            w for w in filtered_watchlist
            if _safe_market(w.get('market', 'us')) == market_filter.upper()
        ]
    if direction_filter != 'All':
        filtered_watchlist = [
            w for w in filtered_watchlist
            if w.get('direction', '').lower() == direction_filter.lower()
        ]

    if not filtered_watchlist:
        st.info("No watchlist stocks match the current filters.")
        return

    # Calculate performance (parallel)
    progress_bar = st.progress(0, text="Loading watchlist performance...")
    performance_data = _process_watchlist_parallel(filtered_watchlist, progress_bar)
    progress_bar.empty()

    perf_df = pd.DataFrame(performance_data)

    if perf_df.empty:
        st.warning("Could not calculate performance data")
        return

    # Sort
    if sort_by == 'Date Added':
        perf_df = perf_df.sort_values('Date Added', ascending=False)
    elif sort_by == 'Score':
        perf_df = perf_df.sort_values('Score', ascending=False)
    elif sort_by == 'P&L %':
        perf_df = perf_df.sort_values('P&L %', ascending=False)
    elif sort_by == 'Symbol':
        perf_df = perf_df.sort_values('Symbol')

    # Summary metrics
    _render_summary_metrics(perf_df)

    # Performance table
    st.subheader("Watchlist Performance")
    _render_performance_table(perf_df)

    # Alerts losing steam section
    losing_steam_df = perf_df[perf_df['Momentum'] == 'Losing Steam']
    if not losing_steam_df.empty:
        st.subheader("⚠️ Losing Steam")
        st.warning(f"{len(losing_steam_df)} stocks are showing weakening momentum - consider removing")
        st.dataframe(
            losing_steam_df[['Symbol', 'Chart', 'Market', 'Date Added', 'Direction', 'Setup', 'Earnings', 'P&L %', 'Max Gain %', 'Days']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'Chart': st.column_config.LinkColumn('📈', display_text='📈', width='small'),
            }
        )

    # Remove from Watchlist section
    st.subheader("Manage Watchlist")
    symbols_in_list = perf_df['Symbol'].tolist()
    raw_symbols = perf_df['_raw_symbol'].tolist()
    symbol_map = dict(zip(symbols_in_list, raw_symbols))

    to_remove = st.multiselect(
        "Select stocks to remove",
        options=symbols_in_list,
        key='wl_remove'
    )

    if to_remove and st.button("🗑️ Remove Selected", key='wl_remove_btn'):
        removed = 0
        for sym in to_remove:
            raw_sym = symbol_map.get(sym, sym)
            if remove_from_watchlist(raw_sym):
                removed += 1
        if removed > 0:
            st.success(f"Removed {removed} stock(s) from watchlist")
            st.rerun()
        else:
            st.warning("Could not remove selected stocks")
