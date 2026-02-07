import streamlit as st
import pandas as pd
from typing import Dict
from screener.support_resistance import detect_levels
from screener.technical_indicators import compute_all
from screener.charts import candlestick_chart


def render(daily_data: Dict[str, pd.DataFrame]):
    st.header("Support & Resistance Levels")

    symbols = sorted(daily_data.keys())
    if not symbols:
        st.info("No data loaded.")
        return

    selected = st.selectbox("Select Stock", symbols, key="sr_stock")
    if not selected or selected not in daily_data:
        return

    df = daily_data[selected]
    lookback = st.slider("Chart lookback (days)", 30, 365, 120, key="sr_lookback")
    df_view = df.tail(lookback)

    resistance, support, pivots = detect_levels(df)

    # Filter S/R levels near current price range
    current = float(df['Close'].iloc[-1])
    price_range = current * 0.15  # show levels within 15% of current price
    resistance_near = [r for r in resistance if abs(r - current) < price_range]
    support_near = [s for s in support if abs(s - current) < price_range]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Support Levels")
        for s in sorted(support_near, reverse=True):
            pct = (current - s) / current * 100
            st.write(f"**{s:.2f}** ({pct:+.1f}% from current)")
    with col2:
        st.subheader("Resistance Levels")
        for r in sorted(resistance_near):
            pct = (r - current) / current * 100
            st.write(f"**{r:.2f}** (+{pct:.1f}% from current)")

    # Classic pivots
    st.subheader("Classic Pivot Points")
    pivot_df = pd.DataFrame([pivots]).T
    pivot_df.columns = ['Price']
    st.dataframe(pivot_df, use_container_width=False)

    # Chart with S/R overlay
    st.subheader("Chart with S/R Levels")
    enriched = compute_all(df_view.copy())
    fig = candlestick_chart(
        enriched, selected,
        overlays=['EMA_20', 'EMA_50'],
        support_levels=support_near[-5:],  # top 5 nearest
        resistance_levels=resistance_near[:5],
    )
    st.plotly_chart(fig, use_container_width=True)
