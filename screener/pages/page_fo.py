import streamlit as st
import pandas as pd
from typing import Dict
from screener.fo_data import get_expiry_dates, get_option_chain, compute_pcr, oi_analysis, get_cache_timestamp
from screener.charts import oi_chart, iv_smile_chart


def render(daily_data: Dict[str, pd.DataFrame]):
    st.header("F&O / Options Chain")

    symbols = sorted(daily_data.keys())
    if not symbols:
        st.info("No data loaded.")
        return

    selected = st.selectbox("Select Stock", symbols, key="fo_stock")
    if not selected:
        return

    expiries, expiry_from_cache = get_expiry_dates(selected)
    if not expiries:
        st.warning(f"No options data available for {selected}. "
                   "Run the screener during market hours (9:15 AM - 3:30 PM IST) "
                   "at least once to cache the data for after-hours use.")
        return

    if expiry_from_cache:
        cache_ts = get_cache_timestamp(selected)
        st.warning(f"Market is closed. Showing cached data from **{cache_ts}**. "
                   "Run during market hours to refresh.")

    selected_expiry = st.selectbox("Expiry Date", expiries)
    if not selected_expiry:
        return

    chain_result, chain_from_cache = get_option_chain(selected, selected_expiry)
    if chain_result is None:
        st.error("Failed to load options chain.")
        return

    calls, puts = chain_result
    current_price = float(daily_data[selected]['Close'].iloc[-1])

    # PCR and OI analysis
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Put-Call Ratio")
        pcr = compute_pcr(calls, puts)
        for key, val in pcr.items():
            st.metric(key, val)

    with col2:
        st.subheader("OI Analysis")
        oi = oi_analysis(calls, puts, current_price)
        for key, val in oi.items():
            st.metric(key, f"{val:.2f}" if isinstance(val, float) else val)

    # OI distribution chart
    st.subheader("Open Interest Distribution")
    fig_oi = oi_chart(calls, puts, current_price)
    st.plotly_chart(fig_oi, use_container_width=True)

    # IV smile
    if 'impliedVolatility' in calls.columns and 'impliedVolatility' in puts.columns:
        st.subheader("IV Smile")
        fig_iv = iv_smile_chart(calls, puts, current_price)
        st.plotly_chart(fig_iv, use_container_width=True)

    # Options chain tables
    st.subheader("Calls")
    display_cols = ['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility']
    available_cols = [c for c in display_cols if c in calls.columns]
    st.dataframe(calls[available_cols].sort_values('strike'), use_container_width=True, hide_index=True)

    st.subheader("Puts")
    available_cols_p = [c for c in display_cols if c in puts.columns]
    st.dataframe(puts[available_cols_p].sort_values('strike'), use_container_width=True, hide_index=True)
