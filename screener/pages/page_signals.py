import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Dict
from screener.data_fetcher import fetch_ohlcv
from screener.fo_data import (
    get_expiry_dates, get_option_chain,
    compute_pcr, compute_max_pain, oi_analysis,
)
from screener.trade_signals import (
    get_index_strategy_signal,
    build_strike_details,
    get_momentum_picks,
    compute_sector_heatmap,
)
from screener.market_mood import fetch_vix
from screener.config import NIFTY_STRIKE_STEP, BANKNIFTY_STRIKE_STEP
from screener.utils import get_chart_url


def _render_strategy_card(signal: dict):
    risk_colors = {'Low': '#2e7d32', 'Medium': '#ef6c00', 'High': '#c62828'}

    st.markdown(f"### {signal['underlying']} -- {signal['strategy']}")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Strategy", signal['strategy'])
    with c2:
        st.metric("Suggested Strikes", signal['strikes'])
    with c3:
        st.metric("Risk Level", signal['risk_level'])

    st.markdown("**Reasoning:**")
    for point in signal['reasoning']:
        st.markdown(f"- {point}")


def _render_strike_details(details: dict):
    """Render the detailed strike table with LTP, IV, OI and P&L summary."""
    if not details or not details.get('legs'):
        return

    st.markdown(f"**Expiry:** `{details['recommended_expiry']}`")

    # Build legs table
    rows = []
    for leg in details['legs']:
        oi_display = leg.get('oi', 0) or 0
        if oi_display >= 1_000_000:
            oi_str = f"{oi_display / 1_000_000:.2f}M"
        elif oi_display >= 1_000:
            oi_str = f"{oi_display / 1_000:.1f}K"
        else:
            oi_str = str(oi_display)

        rows.append({
            'Leg': leg['leg'],
            'Action': leg['action'],
            'Type': leg['type'],
            'Strike': leg['strike'],
            'LTP': leg['ltp'],
            'Bid': leg['bid'],
            'Ask': leg['ask'],
            'IV (%)': leg['iv'],
            'OI': oi_str,
        })

    legs_df = pd.DataFrame(rows)

    def color_action(val):
        if val == 'SELL':
            return 'background-color: #1b5e20; color: white'
        elif val == 'BUY':
            return 'background-color: #b71c1c; color: white'
        return ''

    st.dataframe(
        legs_df.style.map(color_action, subset=['Action']),
        use_container_width=True,
        hide_index=True,
    )

    # P&L summary
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Premium", f"{details['total_premium']:.2f}")
    with m2:
        st.metric("Max Profit", details['max_profit'])
    with m3:
        st.metric("Max Loss", details['max_loss'])
    with m4:
        st.metric("Breakeven Range",
                  f"{details['breakeven_lower']:.0f} - {details['breakeven_upper']:.0f}")


def _render_picks(picks: list, title: str):
    st.markdown(f"#### {title}")
    if not picks:
        st.info("No strong signals found.")
        return

    for pick in picks:
        chart_url = get_chart_url(pick['symbol'])
        with st.expander(
            f"{pick['symbol']} | Score: {pick['score']} | "
            f"Close: {pick['close']}"
        ):
            st.markdown(f"[📈 View Chart]({chart_url})")
            st.markdown(f"**Criteria:** {pick['criteria']}")
            st.markdown(f"**Support:** {pick['support']} | **Resistance:** {pick['resistance']}")
            if pick['direction'] == 'bullish':
                st.markdown(f"**Entry zone:** Near support at **{pick['support']}**")
            else:
                st.markdown(f"**Entry zone:** Near resistance at **{pick['resistance']}**")


def _render_sector_heatmap(sector_df: pd.DataFrame):
    if sector_df.empty:
        st.info("No sector data available (sector map only covers Indian stocks).")
        return

    colors = ['#2e7d32' if v > 0 else '#c62828' for v in sector_df['Avg Net Score']]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sector_df['Sector'],
        y=sector_df['Avg Net Score'],
        marker_color=colors,
        text=sector_df.apply(
            lambda r: f"B:{r['Bullish']} / Be:{r['Bearish']}", axis=1
        ),
        textposition='outside',
    ))
    fig.update_layout(
        title='Sector Sentiment (Avg Net Score: Bullish - Bearish)',
        template='plotly_dark',
        height=400,
        xaxis_title='Sector',
        yaxis_title='Avg Net Score',
    )
    st.plotly_chart(fig, use_container_width=True)

    def color_net(val):
        if isinstance(val, (int, float)):
            if val > 0:
                return 'background-color: #1b5e20; color: white'
            elif val < 0:
                return 'background-color: #b71c1c; color: white'
        return ''

    st.dataframe(
        sector_df.style.map(color_net, subset=['Avg Net Score']),
        use_container_width=True,
        hide_index=True,
    )


def render(daily_data: Dict[str, pd.DataFrame],
           market: str = "indian", index_symbol: str = "^NSEI"):
    st.header("Trade Signals")

    # --- Section 1: Index Strategy Signal ---
    st.subheader("Index Strategy Signal")

    if market == "indian":
        index_options = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
    else:
        index_options = {"S&P 500 (SPY)": "SPY"}

    selected_index = st.selectbox(
        "Select Index", list(index_options.keys()), key="signal_index"
    )
    idx_ticker = index_options[selected_index]

    # Determine strike step
    if 'BANK' in selected_index.upper():
        step = BANKNIFTY_STRIKE_STEP
    else:
        step = NIFTY_STRIKE_STEP

    with st.spinner(f"Analyzing {selected_index}..."):
        price_df = fetch_ohlcv(idx_ticker, period_days=5, interval='1d')
        if price_df is not None and not price_df.empty:
            current_price = float(price_df['Close'].iloc[-1])
        else:
            st.warning(f"Could not fetch price for {idx_ticker}")
            current_price = 0

        if current_price > 0:
            try:
                expiries, _ = get_expiry_dates(idx_ticker)
            except Exception:
                expiries = []

            if not expiries:
                st.warning("No options data available. Indian index options "
                           "may not be supported via yfinance.")
            else:
                # Expiry selector
                selected_expiry = st.selectbox(
                    "Select Expiry",
                    expiries,
                    index=0,
                    help="Nearest expiry selected by default (recommended for short-term strategies)",
                    key="signal_expiry",
                )

                try:
                    chain_result, _ = get_option_chain(idx_ticker, selected_expiry)
                except Exception as e:
                    st.error(f"Error fetching option chain: {e}")
                    chain_result = None

                if chain_result is not None:
                    calls, puts = chain_result
                    pcr = compute_pcr(calls, puts)
                    max_pain = compute_max_pain(calls, puts)
                    oi = oi_analysis(calls, puts, current_price)
                    vix = fetch_vix(market)

                    highest_call_oi = oi.get('Highest Call OI Strike', 0)
                    highest_put_oi = oi.get('Highest Put OI Strike', 0)

                    signal = get_index_strategy_signal(
                        index_name=selected_index,
                        current_price=current_price,
                        max_pain=max_pain,
                        pcr_oi=pcr.get('PCR (OI)', 1.0),
                        vix=vix,
                        highest_call_oi_strike=highest_call_oi,
                        highest_put_oi_strike=highest_put_oi,
                    )
                    _render_strategy_card(signal)

                    # Build and show detailed strike table
                    st.markdown("---")
                    st.subheader("Suggested Option Contracts")

                    try:
                        strike_details = build_strike_details(
                            strategy=signal['strategy'],
                            current_price=current_price,
                            calls=calls,
                            puts=puts,
                            expiries=expiries,
                            selected_expiry=selected_expiry,
                            step=step,
                            highest_call_oi_strike=highest_call_oi,
                            highest_put_oi_strike=highest_put_oi,
                        )
                        _render_strike_details(strike_details)
                    except Exception as e:
                        st.warning(f"Could not build strike details: {e}")
                else:
                    st.info("No option chain data available for this expiry. "
                            "Try selecting a different expiry date.")

    st.markdown("---")

    # --- Section 2: Stock Momentum Picks ---
    st.subheader("Stock Momentum Picks")

    with st.spinner("Finding momentum picks..."):
        bullish_picks, bearish_picks = get_momentum_picks(daily_data, top_n=5)

    col_bull, col_bear = st.columns(2)
    with col_bull:
        _render_picks(bullish_picks, "Top 5 Bullish")
    with col_bear:
        _render_picks(bearish_picks, "Top 5 Bearish")

    st.markdown("---")

    # --- Section 3: Sector Heatmap ---
    st.subheader("Sector Heatmap")

    with st.spinner("Computing sector sentiment..."):
        sector_df = compute_sector_heatmap(daily_data)

    _render_sector_heatmap(sector_df)
