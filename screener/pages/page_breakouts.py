import streamlit as st
import pandas as pd
from typing import Dict
from screener.breakout_detector import scan_batch
from screener.utils import get_chart_url, get_unusual_whales_url


def render(daily_data: Dict[str, pd.DataFrame]):
    st.header("Breakout Detection")

    with st.spinner("Scanning for breakouts..."):
        results = scan_batch(daily_data)

    if results.empty:
        st.info("No breakouts or consolidations detected.")
        return

    col1, col2 = st.columns([1, 2])
    with col1:
        status_filter = st.selectbox("Filter by Status",
                                      ["All", "Breakout Up", "Breakout Down", "Consolidating"])

    filtered = results.copy()
    if status_filter != "All":
        filtered = filtered[filtered['Status'] == status_filter]

    # Add Chart and Option Flow link columns
    filtered['Chart'] = filtered['Symbol'].apply(get_chart_url)
    filtered['Option Flow'] = filtered['Symbol'].apply(get_unusual_whales_url)

    st.markdown(f"**{len(filtered)} stocks found**")

    def color_status(val):
        if val == 'Breakout Up':
            return 'background-color: #1b5e20; color: white'
        elif val == 'Breakout Down':
            return 'background-color: #b71c1c; color: white'
        elif val == 'Consolidating':
            return 'background-color: #e65100; color: white'
        return ''

    st.dataframe(
        filtered.style.map(color_status, subset=['Status']),
        use_container_width=True,
        hide_index=True,
        column_config={
            'Chart': st.column_config.LinkColumn('📈', display_text='📈', width='small'),
            'Option Flow': st.column_config.LinkColumn('Flow', display_text='View', width='small'),
        },
    )

    # Summary metrics
    st.subheader("Summary")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Breakout Up", len(results[results['Status'] == 'Breakout Up']))
    with col_b:
        st.metric("Breakout Down", len(results[results['Status'] == 'Breakout Down']))
    with col_c:
        st.metric("Consolidating", len(results[results['Status'] == 'Consolidating']))
