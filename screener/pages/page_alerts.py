import streamlit as st
import pandas as pd
from typing import Dict, Optional
from datetime import datetime
from screener.alerts import generate_alerts, score_stock, recommend_combo
from screener.alert_history import save_alerts
from screener.utils import get_chart_url, get_unusual_whales_url
from screener.watchlist_store import add_to_watchlist, is_in_watchlist, get_watchlist_symbols
from screener.data_fetcher import fetch_ohlcv
from screener.config import DEFAULT_LOOKBACK_DAYS


def render(daily_data: Dict[str, pd.DataFrame], weekly_data: Dict[str, pd.DataFrame],
           market: str = 'us', index_symbol: str = ''):
    st.header("🔔 Alerts & Summary")

    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        min_score = st.slider("Min alert score", 1, 10, 5)
    with col2:
        signal_filter = st.radio("Filter", ["All", "Bullish Only", "Bearish Only"],
                                 horizontal=True)
    with col3:
        clean_close_only = st.checkbox("Clean Close Only", value=False,
                                        help="Show only stocks where the last candle closed strong in the direction of the alert")

    # Fetch index data for relative strength calculation
    index_df = None
    if index_symbol:
        index_df = fetch_ohlcv(index_symbol, period_days=DEFAULT_LOOKBACK_DAYS)

    with st.spinner("Scoring stocks..."):
        alerts_df = generate_alerts(daily_data, min_score=min_score, index_df=index_df)

    if signal_filter == "Bullish Only":
        alerts_df = alerts_df[alerts_df['Direction'] == 'Bullish']
    elif signal_filter == "Bearish Only":
        alerts_df = alerts_df[alerts_df['Direction'] == 'Bearish']

    total_before_clean = len(alerts_df)

    if clean_close_only and not alerts_df.empty:
        alerts_df = alerts_df[alerts_df['Clean'] == True].reset_index(drop=True)

    if alerts_df.empty:
        if clean_close_only:
            st.info(f"No stocks with clean closes found ({total_before_clean} alerts before filter). Try unchecking the filter.")
        else:
            st.info("No stocks matching criteria at this threshold.")
        return

    clean_count = alerts_df['Clean'].sum() if 'Clean' in alerts_df.columns else 0
    st.markdown(f"**{len(alerts_df)} stocks found** ({clean_count} with clean close)")

    # Action buttons row
    col_save, col_space = st.columns([1, 4])
    with col_save:
        if st.button("Save Alerts to History", help="Save current alerts to track their performance over time"):
            saved = save_alerts(alerts_df, daily_data, market)
            if saved > 0:
                st.success(f"Saved {saved} new alerts! View them in the Tracker tab.")
            else:
                st.info("All alerts already saved for today.")

    # Add Chart and Option Flow link columns
    alerts_df['Chart'] = alerts_df['Symbol'].apply(get_chart_url)
    alerts_df['Option Flow'] = alerts_df['Symbol'].apply(get_unusual_whales_url)

    # Add checkbox column for watchlist selection (pre-checked if already in WL)
    wl_symbols = get_watchlist_symbols()  # Single load instead of per-row calls
    alerts_df.insert(0, 'Add to WL', alerts_df['Symbol'].apply(lambda s: s in wl_symbols))

    # Drop the internal 'Clean' boolean column before display (already used for filtering)
    display_alerts = alerts_df.drop(columns=['Clean'], errors='ignore')

    # Column order: WL checkbox, Symbol, Chart, Option Flow, then the rest
    col_order = [
        'Add to WL', 'Symbol', 'Chart', 'Option Flow',
        'Direction', 'Score', 'RS %', 'Bullish', 'Bearish', 'Close %',
        'Top Criteria', 'Pattern', 'Combo',
    ]

    # Editable dataframe - checkboxes don't cause rerun
    st.caption("Tick the checkbox to select stocks, then click **Add to Watchlist** below")
    edited_df = st.data_editor(
        display_alerts,
        use_container_width=True,
        hide_index=True,
        key='alerts_table',
        column_order=col_order,
        disabled=[c for c in display_alerts.columns if c != 'Add to WL'],  # Only checkbox is editable
        column_config={
            'Add to WL': st.column_config.CheckboxColumn('WL', width='small', help='Select to add to watchlist'),
            'Symbol': st.column_config.TextColumn('Symbol', width='small'),
            'Chart': st.column_config.LinkColumn('Chart', display_text='View', width='small'),
            'Option Flow': st.column_config.LinkColumn('Flow', display_text='View', width='small'),
            'Direction': st.column_config.TextColumn('Direction', width='small'),
            'Score': st.column_config.NumberColumn('Score', width='small'),
            'RS %': st.column_config.NumberColumn('RS %', width='small',
                                                   help='Relative Strength vs index (positive = outperforming)'),
            'Bullish': st.column_config.NumberColumn('Bull', width='small'),
            'Bearish': st.column_config.NumberColumn('Bear', width='small'),
            'Close %': st.column_config.NumberColumn('Close %', width='small',
                                                      help='Where price closed in the day range (100=high, 0=low)'),
            'Top Criteria': st.column_config.TextColumn('Criteria', width='large'),
            'Pattern': st.column_config.TextColumn('Pattern', width='medium'),
            'Combo': st.column_config.TextColumn('Trading Setup', width='medium'),
        },
    )

    # Add to watchlist button - only triggers rerun when clicked
    if st.button("Add Selected to Watchlist", help="Add all checked stocks to your watchlist"):
        # Find rows where checkbox was newly ticked (not already in WL)
        added = 0
        skipped = 0
        for idx, row in edited_df.iterrows():
            if row['Add to WL'] and not is_in_watchlist(row['Symbol']):
                symbol = row['Symbol']
                alert_price = 0.0
                if symbol in daily_data and not daily_data[symbol].empty:
                    alert_price = float(daily_data[symbol]['Close'].iloc[-1])

                today = datetime.now().strftime('%Y-%m-%d')
                result = add_to_watchlist(
                    symbol=symbol,
                    direction=row['Direction'],
                    score=int(row['Score']),
                    alert_price=alert_price,
                    criteria=row.get('Top Criteria', ''),
                    pattern=row.get('Pattern', ''),
                    combo=row.get('Combo', ''),
                    market=market,
                    alert_date=today,
                )
                if result:
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

    st.subheader("🔍 Detail View")
    for _, row in alerts_df.head(20).iterrows():
        with st.expander(f"{row['Symbol']} - {row['Direction']} (Score: {row['Score']})"):
            if row['Symbol'] not in daily_data:
                continue
            result = score_stock(daily_data[row['Symbol']])

            # Combo recommendation
            combo_rec = recommend_combo(
                criteria=result['criteria'],
                signals=result['signals'],
                patterns=result['patterns'],
                is_breakout=result['is_breakout'],
                is_breakdown=result['is_breakdown'],
            )

            if combo_rec['combo'] != 'No clear setup':
                st.success(
                    f"**Recommended Strategy: {combo_rec['combo']}** "
                    f"(match {combo_rec['match_score']}/4)"
                )
                st.caption(f"Reason: {combo_rec['reason']}")
            else:
                st.info(f"**{combo_rec['combo']}** -- {combo_rec['reason']}")

            # Detected patterns
            all_pats = result.get('patterns', {})
            if all_pats:
                bull_p = [p for p, s in all_pats.items() if s == 'bullish']
                bear_p = [p for p, s in all_pats.items() if s == 'bearish']
                if bull_p:
                    st.markdown(f"**Bullish patterns:** :green[{', '.join(bull_p)}]")
                if bear_p:
                    st.markdown(f"**Bearish patterns:** :red[{', '.join(bear_p)}]")

            st.divider()
            st.markdown("**Technical Signals:**")
            for c in result['criteria']:
                if c['signal'] == 'bullish':
                    st.markdown(f"  :green[+] **{c['criterion']}**: {c['detail']}")
                elif c['signal'] == 'bearish':
                    st.markdown(f"  :red[-] **{c['criterion']}**: {c['detail']}")
                else:
                    st.markdown(f"  ~ **{c['criterion']}**: {c['detail']}")

            # Quick link to Unusual Whales
            st.divider()
            uw_url = get_unusual_whales_url(row['Symbol'])
            st.markdown(f"**Option Flow:** [View on Unusual Whales]({uw_url})")

            # Add to watchlist from detail view
            wl_key = f"wl_detail_{row['Symbol']}"
            if is_in_watchlist(row['Symbol']):
                st.caption("Already in watchlist")
            elif st.button(f"Add {row['Symbol']} to Watchlist", key=wl_key):
                alert_price = 0.0
                if row['Symbol'] in daily_data and not daily_data[row['Symbol']].empty:
                    alert_price = float(daily_data[row['Symbol']]['Close'].iloc[-1])
                added = add_to_watchlist(
                    symbol=row['Symbol'],
                    direction=row['Direction'],
                    score=int(row['Score']),
                    alert_price=alert_price,
                    criteria=row.get('Top Criteria', ''),
                    pattern=row.get('Pattern', ''),
                    combo=row.get('Combo', ''),
                    market=market,
                    alert_date=datetime.now().strftime('%Y-%m-%d'),
                )
                if added:
                    st.success(f"Added {row['Symbol']} to watchlist!")
                    st.rerun()
                else:
                    st.info("Already in watchlist")
