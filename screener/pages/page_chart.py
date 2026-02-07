import streamlit as st
import pandas as pd
from typing import Dict
from screener.technical_indicators import compute_all
from screener.support_resistance import detect_levels
from screener.charts import candlestick_chart
from screener.data_fetcher import fetch_ohlcv
from screener.config import WEEKLY_LOOKBACK_DAYS


def render(daily_data: Dict[str, pd.DataFrame], weekly_data: Dict[str, pd.DataFrame]):
    st.header("Interactive Chart")

    symbols = sorted(daily_data.keys())
    if not symbols:
        st.info("No data loaded.")
        return

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected = st.selectbox("Select Stock", symbols, key="chart_stock")
    with col2:
        timeframe = st.radio("Timeframe", ["Daily", "Weekly"], horizontal=True, key="chart_tf")
    with col3:
        lookback = st.slider("Bars", 30, 365, 120, key="chart_lookback")

    if not selected:
        return

    # Get data for selected timeframe
    if timeframe == "Daily":
        df = daily_data.get(selected)
    else:
        df = weekly_data.get(selected)
        if df is None:
            with st.spinner("Fetching weekly data..."):
                df = fetch_ohlcv(selected, period_days=WEEKLY_LOOKBACK_DAYS, interval='1wk')

    if df is None or df.empty:
        st.warning(f"No {timeframe.lower()} data for {selected}")
        return

    df_view = df.tail(lookback)

    # Overlay options
    st.markdown("**Chart Overlays:**")
    overlay_cols = st.columns(6)
    overlays = []
    with overlay_cols[0]:
        if st.checkbox("EMA 20", True, key="ov_ema20"):
            overlays.append('EMA_20')
    with overlay_cols[1]:
        if st.checkbox("EMA 50", True, key="ov_ema50"):
            overlays.append('EMA_50')
    with overlay_cols[2]:
        if st.checkbox("EMA 200", False, key="ov_ema200"):
            overlays.append('EMA_200')
    with overlay_cols[3]:
        if st.checkbox("BB Upper", False, key="ov_bbu"):
            overlays.append('BB_Upper')
        if st.checkbox("BB Lower", False, key="ov_bbl"):
            overlays.append('BB_Lower')
    with overlay_cols[4]:
        if st.checkbox("VWAP", False, key="ov_vwap"):
            overlays.append('VWAP')
    with overlay_cols[5]:
        show_sr = st.checkbox("S/R Levels", False, key="ov_sr")

    show_volume = st.checkbox("Show Volume", True, key="show_vol")
    show_rsi = st.checkbox("Show RSI", True, key="show_rsi")

    # Compute indicators
    enriched = compute_all(df_view.copy())

    # S/R levels
    support_levels = None
    resistance_levels = None
    if show_sr:
        resistance, support, _ = detect_levels(df)
        current = float(df['Close'].iloc[-1])
        price_range = current * 0.15
        resistance_levels = [r for r in resistance if abs(r - current) < price_range][:5]
        support_levels = [s for s in support if abs(s - current) < price_range][-5:]

    fig = candlestick_chart(
        enriched, f"{selected} ({timeframe})",
        overlays=overlays,
        support_levels=support_levels,
        resistance_levels=resistance_levels,
        show_volume=show_volume,
        show_rsi=show_rsi,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Quick stats
    last = enriched.iloc[-1]
    cols = st.columns(6)
    with cols[0]:
        st.metric("Close", f"{last['Close']:.2f}")
    with cols[1]:
        chg = ((last['Close'] - enriched['Close'].iloc[-2]) / enriched['Close'].iloc[-2]) * 100
        st.metric("Change", f"{chg:+.2f}%")
    with cols[2]:
        st.metric("High", f"{last['High']:.2f}")
    with cols[3]:
        st.metric("Low", f"{last['Low']:.2f}")
    with cols[4]:
        vol = last.get('Volume', 0)
        if vol > 1_000_000:
            st.metric("Volume", f"{vol/1_000_000:.1f}M")
        elif vol > 1_000:
            st.metric("Volume", f"{vol/1_000:.1f}K")
        else:
            st.metric("Volume", f"{vol:.0f}")
    with cols[5]:
        rsi = last.get('RSI', None)
        st.metric("RSI", f"{rsi:.1f}" if pd.notna(rsi) else "N/A")
