import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Dict
from screener.market_mood import (
    fetch_vix, compute_breadth, fetch_index_pcr,
    get_mood_label, generate_market_verdict,
)


def render_gauge(mood_score: float) -> go.Figure:
    label, _ = get_mood_label(mood_score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=mood_score,
        title={'text': f"Market Mood: {label}", 'font': {'size': 16}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#FFFFFF"},
            'steps': [
                {'range': [0, 30], 'color': '#c62828'},
                {'range': [30, 45], 'color': '#ef6c00'},
                {'range': [45, 55], 'color': '#fdd835'},
                {'range': [55, 70], 'color': '#66bb6a'},
                {'range': [70, 100], 'color': '#2e7d32'},
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': mood_score,
            },
        },
    ))
    fig.update_layout(
        height=220,
        template='plotly_dark',
        margin=dict(l=20, r=20, t=50, b=10),
    )
    return fig


def render_mood_panel(daily_data: Dict[str, pd.DataFrame],
                      market: str, index_symbol: str):
    st.markdown("---")

    with st.spinner("Calculating market mood..."):
        breadth = compute_breadth(daily_data)
        vix = fetch_vix(market)
        pcr = fetch_index_pcr(index_symbol)

    # Row 1: Gauge + Verdict
    col_gauge, col_verdict = st.columns([1, 2])

    with col_gauge:
        fig = render_gauge(breadth['mood_score'])
        st.plotly_chart(fig, use_container_width=True)

    with col_verdict:
        verdict = generate_market_verdict(breadth['mood_score'], vix, market)
        st.markdown("### Market Verdict")
        st.info(verdict)
        st.markdown(
            f"**Advance/Decline:** "
            f":green[{breadth['bullish_count']} Bullish] / "
            f":red[{breadth['bearish_count']} Bearish] / "
            f"{breadth['neutral_count']} Neutral "
            f"(out of {breadth['total_scored']})"
        )

    # Row 2: Metric cards
    m1, m2, m3, m4, m5 = st.columns(5)

    with m1:
        vix_label = "India VIX" if market == "indian" else "VIX"
        vix_display = f"{vix:.2f}" if vix is not None else "N/A"
        st.metric(vix_label, vix_display)

    with m2:
        pcr_display = f"{pcr:.3f}" if pcr is not None else "N/A"
        st.metric("Index PCR (OI)", pcr_display)

    with m3:
        st.metric("Advance / Decline",
                  f"{breadth['bullish_count']} / {breadth['bearish_count']}")

    with m4:
        st.metric("Stocks > EMA 200", f"{breadth['pct_above_ema200']:.1f}%")

    with m5:
        rsi_val = breadth['avg_rsi']
        rsi_note = None
        if rsi_val > 65:
            rsi_note = "Overbought zone"
        elif rsi_val < 35:
            rsi_note = "Oversold zone"
        st.metric("Avg RSI", f"{rsi_val:.1f}", delta=rsi_note)

    st.markdown("---")
