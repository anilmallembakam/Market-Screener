import streamlit as st
import pandas as pd
from typing import Dict
from screener.technical_indicators import batch_summary, compute_all, generate_signals
from screener.utils import get_chart_url


def render(daily_data: Dict[str, pd.DataFrame]):
    st.header("Technical Indicators")

    with st.spinner("Computing indicators..."):
        summary = batch_summary(daily_data)

    if summary.empty:
        st.info("No data available.")
        return

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        ema_filter = st.selectbox("EMA Trend", ["All", "Strong Bullish", "Bullish",
                                                  "Strong Bearish", "Bearish", "Mixed"])
    with col2:
        rsi_filter = st.selectbox("RSI", ["All", "Oversold (<30)", "Overbought (>70)",
                                           "Neutral (30-70)"])
    with col3:
        macd_filter = st.selectbox("MACD", ["All", "Bullish Crossover", "Bearish Crossover",
                                             "Bullish", "Bearish"])

    filtered = summary.copy()
    if ema_filter != "All":
        filtered = filtered[filtered['EMA_Trend'] == ema_filter]
    if rsi_filter == "Oversold (<30)":
        filtered = filtered[filtered['RSI'] < 30]
    elif rsi_filter == "Overbought (>70)":
        filtered = filtered[filtered['RSI'] > 70]
    elif rsi_filter == "Neutral (30-70)":
        filtered = filtered[(filtered['RSI'] >= 30) & (filtered['RSI'] <= 70)]
    if macd_filter != "All":
        filtered = filtered[filtered['MACD'] == macd_filter]

    st.markdown(f"**{len(filtered)} stocks** (filtered from {len(summary)})")

    # Add Chart link column
    filtered = filtered.copy()
    filtered['Chart'] = filtered['Symbol'].apply(get_chart_url)

    def highlight_rsi(val):
        if pd.isna(val):
            return ''
        if val < 30:
            return 'background-color: #1b5e20; color: white'
        elif val > 70:
            return 'background-color: #b71c1c; color: white'
        return ''

    def highlight_ema(val):
        if 'Bullish' in str(val):
            return 'background-color: #1b5e20; color: white'
        elif 'Bearish' in str(val):
            return 'background-color: #b71c1c; color: white'
        return ''

    styled = filtered.style.map(highlight_rsi, subset=['RSI'])
    styled = styled.map(highlight_ema, subset=['EMA_Trend', 'MACD'])

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Chart': st.column_config.LinkColumn('📈', display_text='📈', width='small'),
        },
    )

    # Detail view
    st.subheader("Stock Detail")
    symbols = sorted(daily_data.keys())
    selected = st.selectbox("Select stock for details", symbols, key="tech_detail_stock")
    if selected and selected in daily_data:
        df = compute_all(daily_data[selected].copy())
        signals = generate_signals(df)
        last = df.iloc[-1]

        cols = st.columns(4)
        with cols[0]:
            st.metric("Close", f"{last['Close']:.2f}")
        with cols[1]:
            rsi_val = last.get('RSI', None)
            st.metric("RSI", f"{rsi_val:.1f}" if pd.notna(rsi_val) else "N/A")
        with cols[2]:
            adx_val = last.get('ADX', None)
            st.metric("ADX", f"{adx_val:.1f}" if pd.notna(adx_val) else "N/A")
        with cols[3]:
            atr_val = last.get('ATR', None)
            st.metric("ATR", f"{atr_val:.2f}" if pd.notna(atr_val) else "N/A")

        st.markdown("**Signals:**")
        for key, val in signals.items():
            st.write(f"- **{key}**: {val}")
