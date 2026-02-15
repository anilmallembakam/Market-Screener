"""Watchlist Monitor page - Track curated stocks with full performance data."""
import streamlit as st
import pandas as pd
from typing import Dict, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from screener.watchlist_store import load_watchlist, remove_from_watchlist
from screener.alert_history import fetch_performance_data, calculate_performance, compute_signal_performance
from screener.alerts import detect_entry_signal
from screener.db import db_save_entry_signals, db_load_active_entry_signals, db_update_entry_signal_status
from screener.utils import get_chart_url


@st.cache_data(ttl=300, show_spinner=False)
def _cached_fetch_watchlist_perf(symbol: str, date_added: str):
    """Fetch performance data from date added until now."""
    days_since = (datetime.now() - datetime.strptime(date_added, '%Y-%m-%d')).days
    track_days = max(days_since + 5, 10)
    return fetch_performance_data(symbol, date_added, track_days)


def _safe_market(val) -> str:
    """Safely get market value as uppercase string."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 'US'
    return str(val).upper()


def _process_single_watchlist_item(item: dict) -> dict:
    """Process a single watchlist item: fetch performance, chart URL."""
    symbol = item['symbol']
    date_added = item.get('date_added', datetime.now().strftime('%Y-%m-%d'))
    item_market = _safe_market(item.get('market', 'us'))

    price_data = _cached_fetch_watchlist_perf(symbol, date_added)
    perf = calculate_performance(item, price_data)
    chart_url = get_chart_url(symbol)

    display_symbol = symbol.replace('.NS', '') if symbol.endswith('.NS') else symbol
    days_in_watchlist = (datetime.now() - datetime.strptime(date_added, '%Y-%m-%d')).days
    alert_date = item.get('alert_date', date_added)

    return {
        'Symbol': display_symbol,
        '_raw_symbol': symbol,
        'Chart': chart_url,
        'Market': item_market,
        'Alert Date': alert_date,
        'Date Added': date_added,
        'Days': days_in_watchlist,
        'Direction': item.get('direction', 'N/A'),
        'Score': item.get('score', 0),
        'Setup': item.get('combo', 'N/A'),
        'Criteria': item.get('criteria', ''),
        'Alert $': item.get('alert_price', 0),
        'Now $': perf['current_price'],
        'P&L %': perf['pnl_pct'],
        'Max Gain %': perf['max_gain_pct'],
        'Max DD %': perf['max_drawdown_pct'],
        'Status': perf['status'],
        'Momentum': perf['momentum'],
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
        'Symbol', 'Chart', 'Market', 'Alert Date', 'Date Added', 'Days',
        'Direction', 'Score', 'Setup', 'Criteria',
        'Alert $', 'Now $', 'P&L %', 'Max Gain %', 'Max DD %',
        'Status', 'Momentum'
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
            'Chart': st.column_config.LinkColumn('Chart', display_text='View', width='small'),
            'Alert Date': st.column_config.TextColumn('Alerted', width='small'),
            'Alert $': st.column_config.NumberColumn('Alert $', format="%.2f"),
            'Now $': st.column_config.NumberColumn('Now $', format="%.2f"),
            'P&L %': st.column_config.NumberColumn('P&L %', format="%.1f%%"),
            'Max Gain %': st.column_config.NumberColumn('Max %', format="%.1f%%"),
            'Max DD %': st.column_config.NumberColumn('DD %', format="%.1f%%"),
        }
    )


def _scan_entry_signals(watchlist_items: list, daily_data: Dict[str, pd.DataFrame]) -> tuple:
    """Scan watchlist items for Trend Following entry signals (bullish + bearish).

    Returns (signals_list, skipped_count) where signals_list contains
    only items with has_signal=True, sorted by strength.
    """
    # Build symbol -> setup mapping from watchlist metadata
    setup_map = {}
    for item in watchlist_items:
        sym = item if isinstance(item, str) else item.get('symbol', '')
        setup = '' if isinstance(item, str) else item.get('combo', 'N/A')
        setup_map[sym] = setup

    signals = []
    skipped = 0
    for sym in setup_map:
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
    watchlist = load_watchlist()

    st.header(f"Watchlist Monitor ({len(watchlist)} stocks)")

    if not watchlist:
        st.info("Your watchlist is empty. Add stocks from the **Alerts/Summary** tab or **Tracker** tab.")
        st.markdown("""
        **How it works:**
        1. Go to the **Alerts/Summary** tab and select rows, then click **Add Selected to Watchlist**
        2. Or go to the **Tracker** tab and add stocks from Live Tracker / Calendar View
        3. Come back here to monitor their performance over time
        """)
        return

    # Sub-tabs
    tab_perf, tab_entry = st.tabs(["📈 Performance", "🎯 Entry Signals"])

    with tab_entry:
        _render_watchlist_entry_tab(watchlist, daily_data, market)

    with tab_perf:
        _render_watchlist_perf_tab(watchlist, market)


def _render_watchlist_entry_tab(watchlist: List[dict], daily_data: Dict[str, pd.DataFrame],
                                market: str = 'us'):
    """Entry Signals tab — saved signals from DB + live scan for new ones."""

    # ── Section A: Saved Signals (from DB) ─────────────────────────────
    st.subheader("Saved Entry Signals")
    st.caption("Loaded from database — persists across sessions")

    saved = db_load_active_entry_signals(source='Watchlist')

    if saved:
        _render_saved_signals_table(saved, daily_data, key_prefix='wl_saved')
    else:
        st.info("No saved entry signals yet. Scan below and save new ones.")

    st.markdown("---")

    # ── Section B: New Signals Detected (live scan) ────────────────────
    st.subheader("New Signals Detected")
    st.caption("Live scan of watchlist — save to track performance")

    with st.spinner("Scanning for entry signals..."):
        entry_signals, entry_skipped = _scan_entry_signals(watchlist, daily_data)

    # Filter out signals already saved (same symbol + today + direction)
    today = datetime.now().strftime('%Y-%m-%d')
    saved_keys = {(s['symbol'], s['signal_date'], s['direction']) for s in saved}
    new_signals = [
        s for s in entry_signals
        if (s['_raw_symbol'], today, s.get('direction', '')) not in saved_keys
    ]

    if new_signals:
        _render_entry_signals(new_signals, entry_skipped, key_prefix='wl_new')

        # Build labels for multiselect
        signal_labels = [
            f"{s['symbol']} ({s.get('direction', '?')}, {s.get('strength', '?')})"
            for s in new_signals
        ]
        selected_labels = st.multiselect(
            "Select signals to save",
            options=signal_labels,
            default=signal_labels,
            key='wl_select_signals'
        )

        col_save1, col_save2, _ = st.columns([1, 1, 2])
        with col_save1:
            save_selected = st.button("Save Selected", key='wl_save_selected_btn',
                                       disabled=len(selected_labels) == 0)
        with col_save2:
            save_all = st.button("Save All", key='wl_save_all_btn')

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
                    'source': 'Watchlist',
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


def _render_saved_signals_table(saved: list, daily_data: Dict[str, pd.DataFrame],
                                 key_prefix: str):
    """Render saved entry signals table with live performance data."""
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
    id_to_sym = {row['_id']: row['Symbol'] for _, row in df.iterrows()}
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


def _render_watchlist_perf_tab(watchlist: List[dict], market: str):
    """Performance tab — existing watchlist performance view."""
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

    # Apply pre-filters
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
        st.subheader("Losing Steam")
        st.warning(f"{len(losing_steam_df)} stocks are showing weakening momentum - consider removing")
        st.dataframe(
            losing_steam_df[['Symbol', 'Chart', 'Market', 'Alert Date', 'Date Added', 'Direction', 'Setup', 'P&L %', 'Max Gain %', 'Days']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'Chart': st.column_config.LinkColumn('Chart', display_text='View', width='small'),
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

    if to_remove and st.button("Remove Selected", key='wl_remove_btn'):
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
