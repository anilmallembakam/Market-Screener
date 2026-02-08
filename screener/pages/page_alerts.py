import streamlit as st
import pandas as pd
from urllib.parse import quote
from typing import Dict
from screener.alerts import generate_alerts, score_stock, recommend_combo
from screener.alert_history import save_alerts


def _get_unusual_whales_url(symbol: str) -> str:
    """Generate Unusual Whales option flow URL for a symbol."""
    # Remove .NS suffix for Indian stocks (UW only supports US stocks)
    ticker = symbol.replace('.NS', '')
    base_url = "https://unusualwhales.com/live-options-flow"
    params = (
        f"?limit=50"
        f"&ticker_symbol={quote(ticker)}"
        f"&excluded_tags[]=no_side"
        f"&excluded_tags[]=mid_side"
        f"&excluded_tags[]=bid_side"
        f"&min_open_interest=1"
        f"&report_flag[]=sweep"
        f"&report_flag[]=floor"
        f"&report_flag[]=normal"
        f"&add_agg_trades=true"
        f"&is_multi_leg=false"
        f"&min_ask_perc=0.6"
    )
    return base_url + params


def render(daily_data: Dict[str, pd.DataFrame], weekly_data: Dict[str, pd.DataFrame], market: str = 'us'):
    st.header("Alerts & Summary")

    col1, col2 = st.columns([1, 3])
    with col1:
        min_score = st.slider("Min alert score", 1, 10, 5)
    with col2:
        signal_filter = st.radio("Filter", ["All", "Bullish Only", "Bearish Only"],
                                 horizontal=True)

    with st.spinner("Scoring stocks..."):
        alerts_df = generate_alerts(daily_data, min_score=min_score)

    if signal_filter == "Bullish Only":
        alerts_df = alerts_df[alerts_df['Direction'] == 'Bullish']
    elif signal_filter == "Bearish Only":
        alerts_df = alerts_df[alerts_df['Direction'] == 'Bearish']

    if alerts_df.empty:
        st.info("No stocks matching criteria at this threshold.")
        return

    st.markdown(f"**{len(alerts_df)} stocks found**")

    # Save alerts to history button
    col_save, col_space = st.columns([1, 4])
    with col_save:
        if st.button("💾 Save Alerts to History", help="Save current alerts to track their performance over time"):
            saved = save_alerts(alerts_df, daily_data, market)
            if saved > 0:
                st.success(f"Saved {saved} new alerts! View them in the 📊 Tracker tab.")
            else:
                st.info("All alerts already saved for today.")

    # Add Unusual Whales link column
    alerts_df['Option Flow'] = alerts_df['Symbol'].apply(_get_unusual_whales_url)

    st.dataframe(
        alerts_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Symbol': st.column_config.TextColumn('Symbol', width='small'),
            'Direction': st.column_config.TextColumn('Direction', width='small'),
            'Score': st.column_config.NumberColumn('Score', width='small'),
            'Bullish': st.column_config.NumberColumn('Bull', width='small'),
            'Bearish': st.column_config.NumberColumn('Bear', width='small'),
            'Top Criteria': st.column_config.TextColumn('Criteria', width='large'),
            'Pattern': st.column_config.TextColumn('Pattern', width='medium'),
            'Combo': st.column_config.TextColumn('Trading Setup', width='medium'),
            'Option Flow': st.column_config.LinkColumn('Option Flow', display_text='View Flow'),
        },
    )

    st.subheader("Detail View")
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

            st.markdown("---")
            st.markdown("**Technical Signals:**")
            for c in result['criteria']:
                if c['signal'] == 'bullish':
                    st.markdown(f"  :green[+] **{c['criterion']}**: {c['detail']}")
                elif c['signal'] == 'bearish':
                    st.markdown(f"  :red[-] **{c['criterion']}**: {c['detail']}")
                else:
                    st.markdown(f"  ~ **{c['criterion']}**: {c['detail']}")

            # Quick link to Unusual Whales
            st.markdown("---")
            uw_url = _get_unusual_whales_url(row['Symbol'])
            st.markdown(f"**Option Flow:** [View on Unusual Whales]({uw_url})")
