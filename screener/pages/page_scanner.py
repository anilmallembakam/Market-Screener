import streamlit as st
import pandas as pd
from typing import Dict
from screener.candlestick_patterns import CANDLESTICK_PATTERNS, scan_batch
from screener.utils import get_chart_url, get_unusual_whales_url


def render(daily_data: Dict[str, pd.DataFrame]):
    st.header("Candlestick Pattern Scanner")

    col1, col2 = st.columns([2, 1])
    with col1:
        pattern_options = {"Scan All Patterns": None}
        pattern_options.update({v: k for k, v in CANDLESTICK_PATTERNS.items()})
        selected_name = st.selectbox("Select Pattern", list(pattern_options.keys()))
        selected_code = pattern_options[selected_name]
    with col2:
        signal_filter = st.radio("Signal Filter", ["All", "Bullish", "Bearish"],
                                 horizontal=True)

    if st.button("Scan", type="primary"):
        with st.spinner("Scanning patterns..."):
            results = scan_batch(daily_data, pattern_filter=selected_code)

        if signal_filter == "Bullish":
            results = results[results['Signal'] == 'bullish']
        elif signal_filter == "Bearish":
            results = results[results['Signal'] == 'bearish']

        if results.empty:
            st.info("No patterns detected.")
            return

        st.markdown(f"**{len(results)} signals found**")

        # Add Chart and Option Flow link columns
        results['Chart'] = results['Symbol'].apply(get_chart_url)
        results['Option Flow'] = results['Symbol'].apply(get_unusual_whales_url)

        def color_signal(val):
            if val == 'bullish':
                return 'background-color: #1b5e20; color: white'
            elif val == 'bearish':
                return 'background-color: #b71c1c; color: white'
            return ''

        st.dataframe(
            results.style.map(color_signal, subset=['Signal']),
            use_container_width=True,
            hide_index=True,
            column_config={
                'Chart': st.column_config.LinkColumn('📈', display_text='📈', width='small'),
                'Option Flow': st.column_config.LinkColumn('Flow', display_text='View', width='small'),
            },
        )

        # Summary counts
        st.subheader("Summary")
        col_a, col_b = st.columns(2)
        with col_a:
            bullish_count = len(results[results['Signal'] == 'bullish'])
            st.metric("Bullish Signals", bullish_count)
        with col_b:
            bearish_count = len(results[results['Signal'] == 'bearish'])
            st.metric("Bearish Signals", bearish_count)

        if selected_code is None:
            # Show pattern frequency
            st.subheader("Pattern Frequency")
            freq = results['Pattern'].value_counts().head(15)
            st.bar_chart(freq)
