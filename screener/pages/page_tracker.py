"""Performance Tracker page - Track historical alerts and their performance."""
import streamlit as st
import pandas as pd
import yfinance as yf
from typing import Dict, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from screener.alert_history import (
    get_historical_alerts,
    fetch_performance_data,
    calculate_performance,
    clear_old_alerts,
    delete_alert,
    get_alerts_by_date,
    get_available_dates,
    get_weekly_summary,
)
from screener.scheduler import (
    run_all_markets_auto_save,
    get_last_auto_save_times,
    is_market_closed,
)
from screener.alerts import detect_entry_signal
from screener.alert_history import compute_signal_performance
from screener.db import db_save_entry_signals, db_load_active_entry_signals, db_update_entry_signal_status
from screener.utils import get_chart_url, get_unusual_whales_url
from screener.watchlist_store import add_to_watchlist, is_in_watchlist, get_watchlist_symbols


# Cache performance data to avoid repeated API calls
@st.cache_data(ttl=300, show_spinner=False)  # Cache for 5 minutes
def _cached_fetch_performance(symbol: str, alert_date: str, track_days: int):
    """Cached wrapper for fetch_performance_data."""
    return fetch_performance_data(symbol, alert_date, track_days)


# Cache earnings data to avoid repeated API calls
@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def _get_earnings_date(symbol: str) -> str:
    """Get next earnings date for a symbol. Returns days until earnings or empty string."""
    try:
        ticker = yf.Ticker(symbol)
        calendar = ticker.calendar

        if calendar is None or calendar.empty:
            return ""

        # Get earnings date
        if 'Earnings Date' in calendar.index:
            earnings_date = calendar.loc['Earnings Date']
            if isinstance(earnings_date, pd.Series):
                earnings_date = earnings_date.iloc[0]
        elif hasattr(calendar, 'columns') and len(calendar.columns) > 0:
            # Sometimes calendar is a DataFrame with dates as columns
            earnings_date = calendar.columns[0]
        else:
            return ""

        if pd.isna(earnings_date):
            return ""

        # Convert to datetime if needed
        if isinstance(earnings_date, str):
            earnings_date = pd.to_datetime(earnings_date)
        elif hasattr(earnings_date, 'to_pydatetime'):
            earnings_date = earnings_date.to_pydatetime()

        # Calculate days until earnings
        today = datetime.now()
        if hasattr(earnings_date, 'tzinfo') and earnings_date.tzinfo is not None:
            earnings_date = earnings_date.replace(tzinfo=None)

        days_until = (earnings_date - today).days

        # If earnings is within 7 days (past or future), show warning
        if -7 <= days_until <= 7:
            if days_until < 0:
                return f"📅 {days_until}d"  # Past (e.g., -1d, -2d)
            elif days_until == 0:
                return "📅 Today!"
            else:
                return f"📅 {days_until}d"  # Future (e.g., 1d, 3d)
        return ""
    except Exception:
        return ""




def _safe_market(val) -> str:
    """Safely get market value as uppercase string."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 'US'
    return str(val).upper()


def _process_single_alert(alert_dict: dict, alert_date: str, track_days: int) -> dict:
    """Process a single alert: fetch performance, earnings, and chart URL.
    Designed to run in a thread pool for parallel execution."""
    symbol = alert_dict['symbol']
    alert_market = _safe_market(alert_dict.get('market', 'us'))

    price_data = _cached_fetch_performance(symbol, alert_date, track_days)
    perf = calculate_performance(alert_dict, price_data)
    earnings_info = _get_earnings_date(symbol)
    chart_url = get_chart_url(symbol)
    uw_url = get_unusual_whales_url(symbol)

    display_symbol = symbol.replace('.NS', '') if symbol.endswith('.NS') else symbol

    return {
        'Symbol': display_symbol,
        'Chart': chart_url,
        'Option Flow': uw_url,
        'Market': alert_market,
        'Alert Date': alert_date,
        'Direction': alert_dict.get('direction', 'N/A'),
        'Score': alert_dict.get('score', 0),
        'Setup': alert_dict.get('combo', 'N/A'),
        'Criteria': alert_dict.get('criteria', ''),
        'Earnings': earnings_info,
        'Alert $': alert_dict.get('alert_price', 0),
        'Now $': perf['current_price'],
        'P&L %': perf['pnl_pct'],
        'Max Gain %': perf['max_gain_pct'],
        'Max DD %': perf['max_drawdown_pct'],
        'Days': perf['days_tracked'],
        'Status': perf['status'],
        'Momentum': perf['momentum'],
        '_raw_symbol': symbol,
        '_pattern': alert_dict.get('pattern', ''),
    }


def _process_alerts_parallel(alerts_df: pd.DataFrame, track_days: int, progress_bar=None) -> List[dict]:
    """Process all alerts in parallel using a thread pool."""
    total = len(alerts_df)
    results = [None] * total  # Preserve order

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_idx = {}
        for idx, (_, alert) in enumerate(alerts_df.iterrows()):
            alert_dict = alert.to_dict()
            alert_date = alert_dict['date']
            future = executor.submit(_process_single_alert, alert_dict, alert_date, track_days)
            future_to_idx[future] = idx

        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                pass  # Skip failed alerts
            completed += 1
            if progress_bar:
                progress_bar.progress(completed / total, text=f"Processing {completed}/{total}...")

    return [r for r in results if r is not None]


def _scan_entry_signals(symbols: list, daily_data: Dict[str, pd.DataFrame],
                        setup_map: dict = None) -> tuple:
    """Scan symbols for Trend Following entry signals (bullish + bearish).

    Returns (signals_list, skipped_count) where signals_list contains
    only items with has_signal=True, sorted by strength.
    setup_map is an optional {raw_symbol: setup_name} dict.
    """
    if setup_map is None:
        setup_map = {}
    signals = []
    skipped = 0
    seen = set()
    for sym in symbols:
        if sym in seen:
            continue
        seen.add(sym)
        if sym not in daily_data:
            skipped += 1
            continue
        results = detect_entry_signal(daily_data[sym], strategy='trend_following')
        for result in results:
            display_sym = sym.replace('.NS', '') if sym.endswith('.NS') else sym
            result['symbol'] = display_sym
            result['_raw_symbol'] = sym
            result['chart_url'] = get_chart_url(sym)
            result['setup'] = setup_map.get(sym, '')
            signals.append(result)

    # Sort: Strong first, then Moderate; within same strength bullish first
    strength_order = {'Strong': 0, 'Moderate': 1}
    dir_order = {'Bullish': 0, 'Bearish': 1}
    signals.sort(key=lambda s: (strength_order.get(s['strength'], 9), dir_order.get(s['direction'], 9)))
    return signals, skipped


def _build_entry_signals_df(signals: list) -> pd.DataFrame:
    """Convert entry signal dicts into a display DataFrame."""
    rows = []
    for sig in signals:
        d = sig['details']
        rows.append({
            'Symbol': sig['symbol'],
            'Chart': sig.get('chart_url', ''),
            'Direction': sig.get('direction', ''),
            'Setup': sig.get('setup', ''),
            'Strength': sig['strength'],
            'Entry $': sig['entry_price'],
            'EMA20': sig['ema20'],
            'Pullback %': sig['pullback_pct'],
            'Stop $': sig['stop_loss'],
            'Target 1': sig['target_1'],
            'Target 2': sig['target_2'],
            'Risk %': sig['risk_pct'],
            'ADX': d.get('adx') if d.get('adx') is not None else 0,
            'RSI': d.get('rsi') if d.get('rsi') is not None else 0,
            'Vol Ratio': d.get('volume_ratio') if d.get('volume_ratio') is not None else 0,
            'Conditions': ', '.join(sig['conditions_met']),
            'Missing': ', '.join(sig['conditions_missing']),
        })
    return pd.DataFrame(rows)


def _render_entry_signals(signals: list, skipped_count: int, key_prefix: str):
    """Render entry signals in a tabular format."""
    total = len(signals)
    strong = sum(1 for s in signals if s['strength'] == 'Strong')
    moderate = total - strong

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Entry Signals", total)
    with col2:
        st.metric("Strong", strong)
    with col3:
        st.metric("Moderate", moderate)
    with col4:
        if skipped_count > 0:
            st.metric("Skipped", skipped_count, help="Stocks not in current data (different market?)")

    # Build and display table
    sig_df = _build_entry_signals_df(signals)

    def color_strength(val):
        if val == 'Strong':
            return 'background-color: #1b5e20; color: white'
        elif val == 'Moderate':
            return 'background-color: #ff8f00; color: black'
        return ''

    def color_direction(val):
        if val == 'Bullish':
            return 'background-color: #1b5e20; color: white'
        elif val == 'Bearish':
            return 'background-color: #b71c1c; color: white'
        return ''

    col_order = [
        'Symbol', 'Chart', 'Direction', 'Setup', 'Strength',
        'Entry $', 'EMA20', 'Pullback %',
        'Stop $', 'Target 1', 'Target 2', 'Risk %',
        'ADX', 'RSI', 'Vol Ratio', 'Conditions', 'Missing',
    ]

    st.dataframe(
        sig_df.style
            .applymap(color_strength, subset=['Strength'])
            .applymap(color_direction, subset=['Direction']),
        use_container_width=True,
        hide_index=True,
        column_order=col_order,
        column_config={
            'Symbol': st.column_config.TextColumn('Symbol', width='small'),
            'Chart': st.column_config.LinkColumn('Chart', display_text='View', width='small'),
            'Direction': st.column_config.TextColumn('Direction', width='small'),
            'Setup': st.column_config.TextColumn('Setup', width='small'),
            'Strength': st.column_config.TextColumn('Signal', width='small'),
            'Entry $': st.column_config.NumberColumn('Entry $', format="%.2f"),
            'EMA20': st.column_config.NumberColumn('EMA20', format="%.2f"),
            'Pullback %': st.column_config.NumberColumn('Pullback %', format="%.1f%%"),
            'Stop $': st.column_config.NumberColumn('Stop $', format="%.2f"),
            'Target 1': st.column_config.NumberColumn('T1 (2:1)', format="%.2f"),
            'Target 2': st.column_config.NumberColumn('T2 (3:1)', format="%.2f"),
            'Risk %': st.column_config.NumberColumn('Risk %', format="%.1f%%"),
            'ADX': st.column_config.NumberColumn('ADX', format="%.0f"),
            'RSI': st.column_config.NumberColumn('RSI', format="%.0f"),
            'Vol Ratio': st.column_config.NumberColumn('Vol', format="%.1fx"),
            'Conditions': st.column_config.TextColumn('Conditions Met', width='large'),
            'Missing': st.column_config.TextColumn('Missing', width='medium'),
        },
    )


def render(daily_data: Dict[str, pd.DataFrame], market: str = 'us'):
    st.header("📊 Performance Tracker")

    # Sub-tabs for different views
    sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5 = st.tabs([
        "📈 Live Tracker",
        "🎯 Entry Signals",
        "📅 Calendar View",
        "📊 Weekly Summary",
        "🔍 Winner Analytics",
    ])

    with sub_tab1:
        _render_live_tracker(daily_data, market)

    with sub_tab2:
        _render_entry_signals_tab(daily_data, market)

    with sub_tab3:
        _render_calendar_view(market)

    with sub_tab4:
        _render_weekly_summary(market)

    with sub_tab5:
        _render_winner_analytics(market)


def _render_live_tracker(daily_data: Dict[str, pd.DataFrame], market: str):
    """Main tracker view with filters and auto-save."""
    st.caption("Performance is calculated from the alert date. Save alerts from the Alerts tab or enable Auto-Save.")

    # Auto-save section
    with st.expander("🤖 Auto-Save Settings", expanded=False):
        st.caption("Auto-save only includes alerts with **Score ≥ 5**")

        col1, col2, col3 = st.columns(3)

        last_saves = get_last_auto_save_times()

        with col1:
            st.markdown("**🇺🇸 US Market**")
            us_status = "✅ Closed" if is_market_closed('us') else "🔴 Open"
            st.caption(f"Status: {us_status}")
            st.caption(f"Last auto-save: {last_saves.get('us', 'Never')}")

        with col2:
            st.markdown("**🇮🇳 Indian Market**")
            in_status = "✅ Closed" if is_market_closed('indian') else "🔴 Open"
            st.caption(f"Status: {in_status}")
            st.caption(f"Last auto-save: {last_saves.get('indian', 'Never')}")

        with col3:
            if st.button("🔄 Run Auto-Save Now", help="Manually trigger auto-save for closed markets (Score ≥ 5)"):
                with st.spinner("Running auto-save..."):
                    results = run_all_markets_auto_save()
                    for mkt, count in results.items():
                        if count > 0:
                            st.success(f"{mkt.upper()}: Saved {count} alerts (Score ≥ 5)")
                        else:
                            st.info(f"{mkt.upper()}: No new alerts or market not closed")

    # Main filters row
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
    with col1:
        market_filter = st.selectbox(
            "Market",
            ['All', 'US', 'Indian'],
            index=1 if market == 'us' else 2,
            key='tracker_market'
        )
    with col2:
        direction_filter = st.selectbox(
            "Direction",
            ['All', 'Bullish', 'Bearish'],
            index=0,
            key='tracker_direction'
        )
    with col3:
        setup_filter = st.selectbox(
            "Setup",
            ['All', 'Trend Following', 'Mean Reversion', 'Breakout', 'Momentum', 'Volatility Squeeze'],
            index=0,
            key='tracker_setup'
        )
    with col4:
        days_back = st.selectbox("Show alerts from last", [7, 14, 30, 60], index=2, key='tracker_days')
    with col5:
        track_days = st.selectbox("Track performance for", [5, 10, 15, 20], index=3, key='tracker_track')

    # Clear old alerts button
    col_clear, _ = st.columns([1, 3])
    with col_clear:
        if st.button("🗑️ Clear alerts older than 60 days"):
            removed = clear_old_alerts(60)
            st.success(f"Removed {removed} old alerts")

    # Convert filter values for query
    market_query = None if market_filter == 'All' else market_filter.lower()
    direction_query = None if direction_filter == 'All' else direction_filter
    setup_query = None if setup_filter == 'All' else setup_filter

    # Load historical alerts with filters
    alerts_df = get_historical_alerts(days_back, market=market_query, direction=direction_query)

    # Filter by setup if specified
    if setup_query and not alerts_df.empty:
        alerts_df = alerts_df[alerts_df['combo'].str.contains(setup_query, case=False, na=False)]

    if alerts_df.empty:
        st.info("No historical alerts found. Save alerts from the Alerts tab or use Auto-Save.")
        st.markdown("""
        **How it works:**
        1. Go to the **Alerts/Summary** tab and click **Save Alerts to History**
        2. Or enable **Auto-Save** to automatically save alerts after market close
        3. Come back here to track their performance over time
        """)
        return

    st.info(f"📋 **{len(alerts_df)} alerts** from the last {days_back} days")

    # Calculate performance for each alert (parallel)
    progress_bar = st.progress(0, text="Calculating performance...")
    performance_data = _process_alerts_parallel(alerts_df, track_days, progress_bar)
    progress_bar.empty()

    perf_df = pd.DataFrame(performance_data)

    if perf_df.empty:
        st.warning("Could not calculate performance data")
        return

    # Summary metrics
    _render_summary_metrics(perf_df)

    # Filter options for table
    st.subheader("📋 Alert Performance")
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.multiselect(
            "Filter by Status",
            ['Winner', 'Gaining', 'Flat', 'Slight Loss', 'Loser'],
            default=[],
            key='status_filter'
        )
    with col2:
        momentum_filter = st.multiselect(
            "Filter by Momentum",
            ['Strong', 'Stable', 'Slowing', 'Losing Steam', 'Too Early'],
            default=[],
            key='momentum_filter'
        )

    # Apply filters
    filtered_df = perf_df.copy()
    if status_filter:
        filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]
    if momentum_filter:
        filtered_df = filtered_df[filtered_df['Momentum'].isin(momentum_filter)]

    # Display table with styling
    _render_performance_table(filtered_df, key='tracker_perf')

    # Alerts losing steam section
    losing_steam_df = perf_df[perf_df['Momentum'] == 'Losing Steam']
    if not losing_steam_df.empty:
        st.subheader("⚠️ Alerts Losing Steam")
        st.warning(f"{len(losing_steam_df)} alerts are showing weakening momentum - consider exiting")
        st.dataframe(
            losing_steam_df[['Symbol', 'Chart', 'Market', 'Alert Date', 'Direction', 'Setup', 'Earnings', 'P&L %', 'Max Gain %', 'Days']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'Chart': st.column_config.LinkColumn('📈', display_text='📈', width='small'),
            }
        )

    # Top and bottom performers side by side
    col_top, col_bottom = st.columns(2)

    with col_top:
        top_df = perf_df.nlargest(5, 'P&L %')
        if not top_df.empty:
            st.subheader("🏆 Top 5 Performers")
            st.dataframe(
                top_df[['Symbol', 'Chart', 'Direction', 'Setup', 'Earnings', 'P&L %', 'Max Gain %', 'Status']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Chart': st.column_config.LinkColumn('📈', display_text='📈', width='small'),
                }
            )

    with col_bottom:
        bottom_df = perf_df.nsmallest(5, 'P&L %')
        if not bottom_df.empty:
            st.subheader("📉 Bottom 5 Performers")
            st.dataframe(
                bottom_df[['Symbol', 'Chart', 'Direction', 'Setup', 'Earnings', 'P&L %', 'Max DD %', 'Status']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Chart': st.column_config.LinkColumn('📈', display_text='📈', width='small'),
                }
            )


def _render_entry_signals_tab(daily_data: Dict[str, pd.DataFrame], market: str):
    """Entry Signals tab — saved signals from DB + live scan for new ones."""

    # ── Section A: Saved Signals (from DB) ─────────────────────────────
    st.subheader("🗂️ Saved Entry Signals")
    st.caption("Persisted across sessions. Close a signal when your trade is done.")

    saved = db_load_active_entry_signals(source='Tracker')

    if saved:
        _render_tracker_saved_signals(saved, daily_data, key_prefix='tracker_saved')
    else:
        st.info("No saved entry signals yet. Run a scan below and save the ones you like.")

    st.divider()

    # ── Section B: New Signals Detected (live scan) ────────────────────
    st.subheader("🔍 New Signals Detected")
    st.caption("Live scan of your tracked stocks for fresh Trend Following entry signals.")

    col1, col2 = st.columns([1, 2])
    with col1:
        days_back = st.selectbox(
            "Scan alerts from last",
            [7, 14, 30, 60],
            index=2,
            key='entry_sig_days'
        )

    # Load tracked symbols
    market_query = market if market != 'all' else None
    alerts_df = get_historical_alerts(days_back, market=market_query)

    if alerts_df.empty:
        st.info("No tracked alerts found. Save alerts from the Alerts tab first.")
        return

    # Build symbol -> setup mapping from historical alerts
    tracker_symbols = alerts_df['symbol'].unique().tolist()
    setup_map = {}
    for _, row in alerts_df.iterrows():
        sym = row.get('symbol', '')
        if sym and sym not in setup_map:
            setup_map[sym] = row.get('combo', '')

    st.markdown(f"Scanning **{len(tracker_symbols)}** unique symbols from {len(alerts_df)} alerts...")

    with st.spinner("Scanning for entry signals..."):
        entry_signals, entry_skipped = _scan_entry_signals(tracker_symbols, daily_data, setup_map)

    # Filter out signals already saved (same symbol + today + direction)
    today = datetime.now().strftime('%Y-%m-%d')
    saved_keys = {(s['symbol'], s['signal_date'], s['direction']) for s in saved}
    new_signals = [
        s for s in entry_signals
        if (s['_raw_symbol'], today, s.get('direction', '')) not in saved_keys
    ]

    if new_signals:
        _render_entry_signals(new_signals, entry_skipped, key_prefix='tracker_entry')

        # Build labels for multiselect
        signal_labels = [
            f"{s['symbol']} ({s.get('direction', '?')}, {s.get('strength', '?')})"
            for s in new_signals
        ]
        selected_labels = st.multiselect(
            "Select signals to save",
            options=signal_labels,
            default=signal_labels,
            key='tracker_select_signals'
        )

        col_save1, col_save2, _ = st.columns([1, 1, 2])
        with col_save1:
            save_selected = st.button("Save Selected", key='tracker_save_selected_btn',
                                       disabled=len(selected_labels) == 0)
        with col_save2:
            save_all = st.button("Save All", key='tracker_save_all_btn')

        signals_to_save = new_signals if save_all else [
            sig for sig, lbl in zip(new_signals, signal_labels) if lbl in selected_labels
        ] if save_selected else []

        if signals_to_save:
            to_save = []
            for sig in signals_to_save:
                d = sig.get('details', {})
                to_save.append({
                    'symbol': sig['_raw_symbol'],
                    'signal_date': today,
                    'direction': sig.get('direction', ''),
                    'strategy': sig.get('strategy', 'Trend Following'),
                    'strength': sig.get('strength', 'Moderate'),
                    'setup': sig.get('setup', ''),
                    'entry_price': sig['entry_price'],
                    'ema20': sig['ema20'],
                    'stop_loss': sig['stop_loss'],
                    'target_1': sig['target_1'],
                    'target_2': sig['target_2'],
                    'risk_pct': sig['risk_pct'],
                    'pullback_pct': sig['pullback_pct'],
                    'adx': d.get('adx'),
                    'rsi': d.get('rsi'),
                    'volume_ratio': d.get('volume_ratio'),
                    'atr': d.get('atr'),
                    'conditions_met': ', '.join(sig.get('conditions_met', [])),
                    'conditions_missing': ', '.join(sig.get('conditions_missing', [])),
                    'source': 'Tracker',
                    'market': market.lower(),
                    'status': 'Active',
                })
            count = db_save_entry_signals(to_save)
            if count > 0:
                st.success(f"Saved {count} new entry signal(s)")
                st.rerun()
            else:
                st.info("Signals already saved (duplicate date/symbol/direction)")
    else:
        msg = "No new entry signals detected."
        if entry_skipped > 0:
            msg += f" ({entry_skipped} stocks skipped — not in current market data)"
        st.info(msg)


def _render_tracker_saved_signals(saved: list, daily_data: Dict[str, pd.DataFrame],
                                   key_prefix: str):
    """Render saved entry signals table with live performance data (Tracker)."""
    rows = []
    for sig in saved:
        raw_sym = sig['symbol']
        display_sym = raw_sym.replace('.NS', '') if raw_sym.endswith('.NS') else raw_sym

        # Get current price from daily_data
        if raw_sym in daily_data and not daily_data[raw_sym].empty:
            current_price = float(daily_data[raw_sym]['Close'].iloc[-1])
        else:
            current_price = sig['entry_price']

        perf = compute_signal_performance(sig, current_price)

        rows.append({
            '_id': sig['id'],
            'Symbol': display_sym,
            'Chart': get_chart_url(raw_sym),
            'Direction': sig['direction'],
            'Setup': sig.get('setup', ''),
            'Strength': sig['strength'],
            'Signal Date': sig['signal_date'],
            'Days Held': perf['days_held'],
            'Entry $': sig['entry_price'],
            'Now $': perf['current_price'],
            'P&L %': perf['pnl_pct'],
            'Stop $': sig['stop_loss'],
            'T1 (2:1)': sig['target_1'],
            'T2 (3:1)': sig['target_2'],
            'Risk %': sig['risk_pct'],
            'Status': perf['status_hint'],
        })

    df = pd.DataFrame(rows)

    # Summary metrics
    total = len(df)
    active = len(df[df['Status'] == 'Active'])
    winners = len(df[df['P&L %'] > 0])
    avg_pnl = df['P&L %'].mean() if total > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Signals", total)
    with c2:
        st.metric("Active", active)
    with c3:
        st.metric("Profitable", winners)
    with c4:
        st.metric("Avg P&L", f"{avg_pnl:.1f}%")

    def color_pnl(val):
        if val >= 5:
            return 'background-color: #1b5e20; color: white'
        elif val >= 0:
            return 'background-color: #2e7d32; color: white'
        elif val >= -5:
            return 'background-color: #ff8f00; color: black'
        else:
            return 'background-color: #b71c1c; color: white'

    def color_status(val):
        if val == 'Target Hit':
            return 'background-color: #1b5e20; color: white'
        elif val == 'Stopped Out':
            return 'background-color: #b71c1c; color: white'
        elif val == 'Active':
            return 'background-color: #1565c0; color: white'
        return ''

    display_cols = [c for c in df.columns if c != '_id']

    st.dataframe(
        df[display_cols].style
            .applymap(color_pnl, subset=['P&L %'])
            .applymap(color_status, subset=['Status']),
        use_container_width=True,
        hide_index=True,
        column_config={
            'Symbol': st.column_config.TextColumn('Symbol', width='small'),
            'Chart': st.column_config.LinkColumn('Chart', display_text='View', width='small'),
            'Direction': st.column_config.TextColumn('Dir', width='small'),
            'Setup': st.column_config.TextColumn('Setup', width='small'),
            'Strength': st.column_config.TextColumn('Signal', width='small'),
            'Signal Date': st.column_config.TextColumn('Triggered', width='small'),
            'Days Held': st.column_config.NumberColumn('Days', format="%d"),
            'Entry $': st.column_config.NumberColumn('Entry $', format="%.2f"),
            'Now $': st.column_config.NumberColumn('Now $', format="%.2f"),
            'P&L %': st.column_config.NumberColumn('P&L %', format="%.1f%%"),
            'Stop $': st.column_config.NumberColumn('Stop $', format="%.2f"),
            'T1 (2:1)': st.column_config.NumberColumn('T1', format="%.2f"),
            'T2 (3:1)': st.column_config.NumberColumn('T2', format="%.2f"),
            'Risk %': st.column_config.NumberColumn('Risk %', format="%.1f%%"),
            'Status': st.column_config.TextColumn('Status', width='small'),
        },
    )

    # Close signals management
    options = [f"{row['Symbol']} ({row['Direction']}, {row['Signal Date']})" for _, row in df.iterrows()]
    id_list = df['_id'].tolist()

    to_close = st.multiselect("Select signals to close", options=options, key=f'{key_prefix}_close')

    if to_close and st.button("Close Selected", key=f'{key_prefix}_close_btn'):
        closed = 0
        for label in to_close:
            idx = options.index(label)
            sig_id = id_list[idx]
            now_price = df.iloc[idx]['Now $']
            if db_update_entry_signal_status(
                sig_id, 'Closed',
                exit_price=now_price,
                exit_date=datetime.now().strftime('%Y-%m-%d')
            ):
                closed += 1
        if closed > 0:
            st.success(f"Closed {closed} signal(s)")
            st.rerun()


def _render_calendar_view(market: str):
    """Calendar-based historical view of alerts."""
    st.caption("Select a past date to see which alerts were triggered and how they performed since then.")

    # Get available dates
    available_dates = get_available_dates()

    if not available_dates:
        st.info("No historical alerts found. Save some alerts first!")
        return

    col1, col2 = st.columns([1, 1])

    with col1:
        # Date selector
        min_date = datetime.strptime(min(available_dates), '%Y-%m-%d').date()
        max_date = datetime.strptime(max(available_dates), '%Y-%m-%d').date()

        selected_date = st.date_input(
            "Select Alert Date",
            value=datetime.strptime(available_dates[0], '%Y-%m-%d').date(),
            min_value=min_date,
            max_value=max_date,
            key='calendar_date'
        )

    with col2:
        market_filter = st.selectbox(
            "Market",
            ['All', 'US', 'Indian'],
            index=0,
            key='calendar_market'
        )

    date_str = selected_date.strftime('%Y-%m-%d')
    market_query = None if market_filter == 'All' else market_filter.lower()

    # Check if this date has alerts
    if date_str not in available_dates:
        st.warning(f"No alerts found for {date_str}. Try selecting a different date.")
        st.markdown("**Dates with alerts:**")
        for d in available_dates[:10]:
            st.caption(f"• {d}")
        return

    # Get alerts for selected date
    alerts_df = get_alerts_by_date(date_str, market_query)

    if alerts_df.empty:
        st.info(f"No alerts for {date_str} in {market_filter} market")
        return

    # Calculate days since alert
    days_since = (datetime.now() - datetime.strptime(date_str, '%Y-%m-%d')).days

    st.markdown(f"### Alerts from {date_str}")
    st.caption(f"**{len(alerts_df)} alerts** | Tracking for **{days_since} days**")

    # Calculate performance till today (parallel)
    progress_bar = st.progress(0, text="Calculating performance...")
    performance_data = _process_alerts_parallel(alerts_df, days_since, progress_bar)
    progress_bar.empty()

    perf_df = pd.DataFrame(performance_data)

    if not perf_df.empty:
        # Summary for this date
        _render_summary_metrics(perf_df)

        # Performance table
        _render_performance_table(perf_df, key='calendar_perf')


def _render_weekly_summary(market: str):
    """Weekly performance summary report."""
    st.caption("Aggregated win rate, average P&L, and top/worst performers for the selected period.")

    col1, col2 = st.columns([1, 2])

    with col1:
        weeks_back = st.selectbox(
            "Report Period",
            [1, 2, 4, 8],
            index=0,
            format_func=lambda x: f"Last {x} week{'s' if x > 1 else ''}",
            key='weekly_weeks'
        )

    with col2:
        market_filter = st.selectbox(
            "Market",
            ['All', 'US', 'Indian'],
            index=0,
            key='weekly_market'
        )

    market_query = None if market_filter == 'All' else market_filter.lower()

    with st.spinner("Generating weekly summary..."):
        summary = get_weekly_summary(weeks_back, market_query)

    if summary['total_alerts'] == 0:
        st.info(f"No alerts found in the last {weeks_back} week(s)")
        return

    # Header
    st.markdown(f"### Weekly Report: {summary['period_start']} to {summary['period_end']}")

    # Main metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Alerts", summary['total_alerts'])
    with col2:
        st.metric("Winners (>5%)", summary['winners'],
                  delta=f"{summary['win_rate']}% win rate")
    with col3:
        st.metric("Losers (<-5%)", summary['losers'],
                  delta_color="inverse")
    with col4:
        delta_color = "normal" if summary['avg_pnl'] >= 0 else "inverse"
        st.metric("Avg P&L", f"{summary['avg_pnl']}%",
                  delta="Profitable" if summary['avg_pnl'] > 0 else "Losing")
    with col5:
        st.metric("Losing Steam", summary['losing_steam_count'],
                  delta="Watch!" if summary['losing_steam_count'] > 0 else None,
                  delta_color="off")

    st.markdown("---")

    # Performance by Direction
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📊 By Direction")
        if summary['by_direction']:
            for direction, stats in summary['by_direction'].items():
                emoji = "🟢" if direction == "Bullish" else "🔴"
                st.markdown(f"""
                **{emoji} {direction}**
                - Alerts: {stats['count']}
                - Avg P&L: {stats['avg_pnl']}%
                - Win Rate: {stats['win_rate']}%
                """)
        else:
            st.caption("No data")

    with col2:
        st.markdown("#### 🌍 By Market")
        if summary['by_market']:
            for mkt, stats in summary['by_market'].items():
                flag = "🇺🇸" if mkt == "US" else "🇮🇳"
                st.markdown(f"""
                **{flag} {mkt}**
                - Alerts: {stats['count']}
                - Avg P&L: {stats['avg_pnl']}%
                - Win Rate: {stats['win_rate']}%
                """)
        else:
            st.caption("No data")

    st.markdown("---")

    # Best and Worst performers
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🏆 Best Performer")
        if summary['best_performer']:
            best = summary['best_performer']
            st.success(f"""
            **{best['symbol']}**
            - P&L: +{best['pnl_pct']}%
            - Max Gain: {best['max_gain_pct']}%
            - Direction: {best['direction']}
            """)
        else:
            st.caption("No data")

    with col2:
        st.markdown("#### 📉 Worst Performer")
        if summary['worst_performer']:
            worst = summary['worst_performer']
            st.error(f"""
            **{worst['symbol']}**
            - P&L: {worst['pnl_pct']}%
            - Max DD: {worst['max_drawdown_pct']}%
            - Direction: {worst['direction']}
            """)
        else:
            st.caption("No data")


def _render_summary_metrics(perf_df: pd.DataFrame):
    """Render summary metrics row."""
    st.subheader("📊 Performance Summary")
    col1, col2, col3, col4, col5 = st.columns(5)

    winners = len(perf_df[perf_df['P&L %'] >= 5])
    losers = len(perf_df[perf_df['P&L %'] <= -5])
    flat = len(perf_df) - winners - losers
    avg_pnl = perf_df['P&L %'].mean()
    losing_steam = len(perf_df[perf_df['Momentum'] == 'Losing Steam'])

    with col1:
        st.metric("🟢 Winners (>5%)", winners, delta=f"{winners/len(perf_df)*100:.0f}% win rate")
    with col2:
        st.metric("🔴 Losers (<-5%)", losers, delta=f"-{losers/len(perf_df)*100:.0f}%", delta_color="inverse")
    with col3:
        st.metric("⚪ Flat", flat, help="P&L between -5% and +5%")
    with col4:
        st.metric("📈 Avg P&L", f"{avg_pnl:.1f}%", delta="Profitable" if avg_pnl > 0 else "Unprofitable", delta_color="normal" if avg_pnl >= 0 else "inverse")
    with col5:
        st.metric("⚠️ Losing Steam", losing_steam, delta="Exit candidates" if losing_steam > 0 else "None", delta_color="off")


def _render_performance_table(perf_df: pd.DataFrame, key: str = 'perf_table', editable: bool = True):
    """Render styled performance dataframe with optional checkbox for watchlist."""
    # Style functions
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

    # Filter out internal columns from display
    display_cols = [c for c in perf_df.columns if not c.startswith('_')]

    if editable:
        # Add checkbox column for watchlist selection (single load for efficiency)
        wl_symbols = get_watchlist_symbols()
        edit_df = perf_df[display_cols].copy()
        # Build a mapping from display symbol to raw symbol for WL check
        raw_sym_map = {}
        if '_raw_symbol' in perf_df.columns:
            for i, row in perf_df.iterrows():
                raw_sym_map[row['Symbol']] = row['_raw_symbol']
        edit_df.insert(0, 'Add to WL', edit_df['Symbol'].apply(
            lambda s: raw_sym_map.get(s, s) in wl_symbols
        ))

        # Column order: WL, Symbol, Chart first, then the rest
        tracker_col_order = [
            'Add to WL', 'Symbol', 'Chart', 'Option Flow',
            'Market', 'Alert Date', 'Direction', 'Score', 'Setup', 'Criteria',
            'Earnings', 'Alert $', 'Now $', 'P&L %', 'Max Gain %', 'Max DD %',
            'Days', 'Status', 'Momentum',
        ]

        st.caption("Tick the checkbox to select stocks, then click **Add to Watchlist** below")
        edited_df = st.data_editor(
            edit_df,
            use_container_width=True,
            hide_index=True,
            key=key,
            column_order=tracker_col_order,
            disabled=[c for c in edit_df.columns if c != 'Add to WL'],
            column_config={
                'Add to WL': st.column_config.CheckboxColumn('WL', width='small', help='Select to add to watchlist'),
                'Symbol': st.column_config.TextColumn('Symbol', width='small'),
                'Chart': st.column_config.LinkColumn('Chart', display_text='View', width='small'),
                'Option Flow': st.column_config.LinkColumn('Flow', display_text='View', width='small'),
                'Alert $': st.column_config.NumberColumn('Alert $', format="%.2f"),
                'Now $': st.column_config.NumberColumn('Now $', format="%.2f"),
                'P&L %': st.column_config.NumberColumn('P&L %', format="%.1f%%"),
                'Max Gain %': st.column_config.NumberColumn('Max %', format="%.1f%%"),
                'Max DD %': st.column_config.NumberColumn('DD %', format="%.1f%%"),
            }
        )

        # Add to watchlist button
        if st.button("Add Selected to Watchlist", key=f'{key}_wl_btn', help="Add all checked stocks to your watchlist"):
            added = 0
            skipped = 0
            for idx, row in edited_df.iterrows():
                if row['Add to WL']:
                    # Get the raw symbol from perf_df
                    raw_sym = perf_df.iloc[idx].get('_raw_symbol', row['Symbol'])
                    if is_in_watchlist(raw_sym):
                        continue
                    alert_date = row.get('Alert Date', datetime.now().strftime('%Y-%m-%d'))
                    ok = add_to_watchlist(
                        symbol=raw_sym,
                        direction=row['Direction'],
                        score=int(row['Score']),
                        alert_price=float(row.get('Alert $', 0)),
                        criteria=row.get('Criteria', ''),
                        pattern=perf_df.iloc[idx].get('_pattern', ''),
                        combo=row.get('Setup', ''),
                        market=row.get('Market', 'US').lower(),
                        alert_date=alert_date,
                    )
                    if ok:
                        added += 1
                    else:
                        skipped += 1
            if added > 0:
                st.success(f"Added {added} stock(s) to watchlist!")
                st.rerun()
            elif skipped > 0:
                st.info("Selected stocks are already in watchlist")
            else:
                st.warning("No new stocks selected. Tick the checkboxes first.")
    else:
        # Non-editable display (for weekly summary, analytics, etc.)
        display_df = perf_df[display_cols]
        # Column order: Symbol, Chart first
        readonly_col_order = [
            'Symbol', 'Chart', 'Option Flow',
            'Market', 'Alert Date', 'Direction', 'Score', 'Setup', 'Criteria',
            'Earnings', 'Alert $', 'Now $', 'P&L %', 'Max Gain %', 'Max DD %',
            'Days', 'Status', 'Momentum',
        ]
        st.dataframe(
            display_df.style
                .applymap(color_pnl, subset=['P&L %'])
                .applymap(color_momentum, subset=['Momentum']),
            use_container_width=True,
            hide_index=True,
            column_order=readonly_col_order,
            column_config={
                'Symbol': st.column_config.TextColumn('Symbol', width='small'),
                'Chart': st.column_config.LinkColumn('Chart', display_text='View', width='small'),
                'Option Flow': st.column_config.LinkColumn('Flow', display_text='View', width='small'),
                'Alert $': st.column_config.NumberColumn('Alert $', format="%.2f"),
                'Now $': st.column_config.NumberColumn('Now $', format="%.2f"),
                'P&L %': st.column_config.NumberColumn('P&L %', format="%.1f%%"),
                'Max Gain %': st.column_config.NumberColumn('Max %', format="%.1f%%"),
                'Max DD %': st.column_config.NumberColumn('DD %', format="%.1f%%"),
            }
        )


def _render_winner_analytics(market: str):
    """Analyze common factors among winning alerts."""
    st.caption("Find common patterns, setups, and criteria among your best-performing alerts.")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        days_back = st.selectbox("Analyze alerts from last", [14, 30, 60, 90], index=1, key='analytics_days')
    with col2:
        min_pnl = st.selectbox("Winner threshold (P&L %)", [3, 5, 10, 15], index=1, key='analytics_pnl')
    with col3:
        market_filter = st.selectbox("Market", ['All', 'US', 'Indian'], index=0, key='analytics_market')

    market_query = None if market_filter == 'All' else market_filter.lower()

    # Get all alerts
    alerts_df = get_historical_alerts(days_back, market=market_query)

    if alerts_df.empty:
        st.info("No alerts found for analysis. Save more alerts first!")
        return

    # Calculate performance for all alerts (parallel)
    def _process_analytics_alert(alert_dict: dict) -> dict:
        symbol = alert_dict['symbol']
        alert_date = alert_dict['date']
        price_data = _cached_fetch_performance(symbol, alert_date, 20)
        perf = calculate_performance(alert_dict, price_data)
        return {
            'symbol': symbol,
            'date': alert_date,
            'direction': alert_dict.get('direction', 'N/A'),
            'score': alert_dict.get('score', 0),
            'criteria': alert_dict.get('criteria', ''),
            'pattern': alert_dict.get('pattern', ''),
            'combo': alert_dict.get('combo', ''),
            'market': _safe_market(alert_dict.get('market', 'us')),
            'pnl_pct': perf['pnl_pct'],
            'max_gain_pct': perf['max_gain_pct'],
            'status': perf['status'],
        }

    all_performance = []
    with st.spinner("Analyzing alerts..."):
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(_process_analytics_alert, alert.to_dict())
                for _, alert in alerts_df.iterrows()
            ]
            for future in as_completed(futures):
                try:
                    all_performance.append(future.result())
                except Exception:
                    pass

    perf_df = pd.DataFrame(all_performance)

    if perf_df.empty:
        st.warning("Could not calculate performance data")
        return

    # Split into winners and losers
    winners_df = perf_df[perf_df['pnl_pct'] >= min_pnl]
    losers_df = perf_df[perf_df['pnl_pct'] <= -min_pnl]
    total = len(perf_df)

    # Summary
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Alerts", total)
    with col2:
        st.metric("Winners", len(winners_df), delta=f"{len(winners_df)/total*100:.0f}%")
    with col3:
        st.metric("Losers", len(losers_df), delta=f"-{len(losers_df)/total*100:.0f}%", delta_color="inverse")
    with col4:
        avg_winner = winners_df['pnl_pct'].mean() if not winners_df.empty else 0
        st.metric("Avg Winner P&L", f"{avg_winner:.1f}%")

    if winners_df.empty:
        st.warning(f"No winners found with P&L >= {min_pnl}%. Try lowering the threshold.")
        return

    st.markdown("---")
    st.subheader("🔍 What Makes Winners Win?")

    # Analysis columns
    col1, col2 = st.columns(2)

    with col1:
        # Score Distribution
        st.markdown("#### 📊 Score Distribution")
        score_analysis = winners_df.groupby('score').agg({
            'symbol': 'count',
            'pnl_pct': 'mean'
        }).rename(columns={'symbol': 'Count', 'pnl_pct': 'Avg P&L %'}).round(1)
        score_analysis = score_analysis.sort_index(ascending=False)

        if not score_analysis.empty:
            best_score = score_analysis['Avg P&L %'].idxmax()
            st.success(f"**Best performing score: {best_score}** (Avg P&L: {score_analysis.loc[best_score, 'Avg P&L %']:.1f}%)")
            st.dataframe(score_analysis, use_container_width=True)

    with col2:
        # Direction Analysis
        st.markdown("#### 🎯 Direction Analysis")
        dir_winners = winners_df.groupby('direction').agg({
            'symbol': 'count',
            'pnl_pct': 'mean'
        }).rename(columns={'symbol': 'Winners', 'pnl_pct': 'Avg P&L %'}).round(1)

        dir_all = perf_df.groupby('direction').size().rename('Total')
        dir_analysis = dir_winners.join(dir_all)
        dir_analysis['Win Rate %'] = (dir_analysis['Winners'] / dir_analysis['Total'] * 100).round(1)

        if not dir_analysis.empty:
            best_dir = dir_analysis['Win Rate %'].idxmax()
            st.success(f"**Best direction: {best_dir}** (Win Rate: {dir_analysis.loc[best_dir, 'Win Rate %']:.0f}%)")
            st.dataframe(dir_analysis[['Winners', 'Total', 'Win Rate %', 'Avg P&L %']], use_container_width=True)

    st.markdown("---")

    # Pattern Analysis
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📈 Winning Patterns")
        # Extract patterns from winners
        pattern_counts = {}
        for patterns in winners_df['pattern'].dropna():
            if patterns and str(patterns) != 'nan':
                for p in str(patterns).split(','):
                    p = p.strip()
                    if p:
                        pattern_counts[p] = pattern_counts.get(p, 0) + 1

        if pattern_counts:
            pattern_df = pd.DataFrame([
                {'Pattern': k, 'Count': v, 'Win %': round(v / len(winners_df) * 100, 1)}
                for k, v in sorted(pattern_counts.items(), key=lambda x: -x[1])[:10]
            ])
            st.success(f"**Top pattern: {pattern_df.iloc[0]['Pattern']}** ({pattern_df.iloc[0]['Count']} winners)")
            st.dataframe(pattern_df, use_container_width=True, hide_index=True)
        else:
            st.info("No pattern data available")

    with col2:
        st.markdown("#### 🎲 Winning Setups (Combo)")
        # Extract combos from winners
        combo_counts = {}
        for combo in winners_df['combo'].dropna():
            if combo and str(combo) != 'nan' and str(combo) != 'No clear setup':
                combo = str(combo).strip()
                if combo:
                    combo_counts[combo] = combo_counts.get(combo, 0) + 1

        if combo_counts:
            combo_df = pd.DataFrame([
                {'Setup': k, 'Count': v, 'Win %': round(v / len(winners_df) * 100, 1)}
                for k, v in sorted(combo_counts.items(), key=lambda x: -x[1])[:10]
            ])
            st.success(f"**Top setup: {combo_df.iloc[0]['Setup']}** ({combo_df.iloc[0]['Count']} winners)")
            st.dataframe(combo_df, use_container_width=True, hide_index=True)
        else:
            st.info("No setup/combo data available")

    st.markdown("---")

    # Criteria Analysis
    st.markdown("#### 🔑 Key Criteria in Winners")
    criteria_counts = {}
    for criteria in winners_df['criteria'].dropna():
        if criteria and str(criteria) != 'nan':
            for c in str(criteria).split(','):
                c = c.strip()
                if c:
                    criteria_counts[c] = criteria_counts.get(c, 0) + 1

    if criteria_counts:
        # Sort and get top 15
        top_criteria = sorted(criteria_counts.items(), key=lambda x: -x[1])[:15]
        criteria_df = pd.DataFrame([
            {'Criteria': k, 'Appearances': v, '% of Winners': round(v / len(winners_df) * 100, 1)}
            for k, v in top_criteria
        ])

        st.success(f"**Most common criteria: {criteria_df.iloc[0]['Criteria']}** (in {criteria_df.iloc[0]['% of Winners']:.0f}% of winners)")

        # Display as bar chart
        st.bar_chart(criteria_df.set_index('Criteria')['Appearances'])
        st.dataframe(criteria_df, use_container_width=True, hide_index=True)
    else:
        st.info("No criteria data available")

    st.markdown("---")

    # Winners vs Losers Comparison
    st.markdown("#### ⚔️ Winners vs Losers Comparison")

    if not losers_df.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Winners Profile**")
            st.markdown(f"""
            - Avg Score: **{winners_df['score'].mean():.1f}**
            - Avg P&L: **+{winners_df['pnl_pct'].mean():.1f}%**
            - Avg Max Gain: **{winners_df['max_gain_pct'].mean():.1f}%**
            - Most Common Direction: **{winners_df['direction'].mode().iloc[0] if not winners_df['direction'].mode().empty else 'N/A'}**
            """)

        with col2:
            st.markdown("**Losers Profile**")
            st.markdown(f"""
            - Avg Score: **{losers_df['score'].mean():.1f}**
            - Avg P&L: **{losers_df['pnl_pct'].mean():.1f}%**
            - Avg Max Gain: **{losers_df['max_gain_pct'].mean():.1f}%**
            - Most Common Direction: **{losers_df['direction'].mode().iloc[0] if not losers_df['direction'].mode().empty else 'N/A'}**
            """)

        # Score comparison
        st.markdown("**Score Comparison**")
        comparison_data = {
            'Metric': ['Avg Score', 'Score 5', 'Score 6', 'Score 7', 'Score 8+'],
            'Winners': [
                round(winners_df['score'].mean(), 1),
                len(winners_df[winners_df['score'] == 5]),
                len(winners_df[winners_df['score'] == 6]),
                len(winners_df[winners_df['score'] == 7]),
                len(winners_df[winners_df['score'] >= 8]),
            ],
            'Losers': [
                round(losers_df['score'].mean(), 1),
                len(losers_df[losers_df['score'] == 5]),
                len(losers_df[losers_df['score'] == 6]),
                len(losers_df[losers_df['score'] == 7]),
                len(losers_df[losers_df['score'] >= 8]),
            ],
        }
        st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)
    else:
        st.info(f"No losers with P&L <= -{min_pnl}% found for comparison")

    # Top Winners List
    st.markdown("---")
    st.markdown("#### 🏆 Top 10 Winners")
    top_winners = winners_df.nlargest(10, 'pnl_pct')[['symbol', 'date', 'direction', 'score', 'pattern', 'combo', 'pnl_pct']]
    top_winners.columns = ['Symbol', 'Date', 'Direction', 'Score', 'Pattern', 'Setup', 'P&L %']
    st.dataframe(top_winners, use_container_width=True, hide_index=True)
