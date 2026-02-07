import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict
from screener.backtester import backtest_combo


def render(daily_data: Dict[str, pd.DataFrame]):
    """Render the backtesting tab for combo strategies."""
    st.header("Backtest Trading Combos")

    st.info(
        "Test the historical performance of the 4 trading combo strategies. "
        "The engine walks through past data, detects combo signals, and "
        "tracks returns after 5, 10, and 20 days."
    )

    # ── Controls ──
    col1, col2, col3 = st.columns(3)

    with col1:
        combo = st.selectbox(
            "Trading Combo",
            ['Trend Following', 'Mean Reversion', 'Breakout', 'Sell/Short'],
            key='bt_combo',
        )

    with col2:
        lookback_label = st.selectbox(
            "Lookback Period",
            ['6 months', '1 year', '2 years'],
            index=1,
            key='bt_lookback',
        )
        lookback_days = {'6 months': 126, '1 year': 252, '2 years': 504}[lookback_label]

    with col3:
        run_mode = st.radio("Mode", ['Single Stock', 'All Stocks'],
                            horizontal=True, key='bt_mode')

    symbols_list = sorted(daily_data.keys())

    # ── Single Stock ──
    if run_mode == 'Single Stock':
        selected = st.selectbox("Select Stock", symbols_list, key='bt_symbol')
        if st.button("Run Backtest", type="primary", key='bt_run_single'):
            with st.spinner(f"Backtesting {combo} on {selected}..."):
                result = backtest_combo(
                    daily_data[selected], selected, combo, lookback_days,
                )
            _display_single(result)

    # ── All Stocks ──
    else:
        if st.button("Run Backtest on All Stocks", type="primary", key='bt_run_batch'):
            progress = st.progress(0)
            results = []
            total = len(daily_data)
            for idx, (sym, df) in enumerate(daily_data.items()):
                res = backtest_combo(df, sym, combo, lookback_days)
                if res['total_signals'] > 0:
                    results.append(res)
                progress.progress((idx + 1) / total)
            progress.empty()
            _display_batch(results, combo)


# ── Display helpers ───────────────────────────────────────────────────────

def _display_single(result: dict):
    st.subheader(f"Results: {result['symbol']} -- {result['combo']}")

    if result['total_signals'] == 0:
        st.warning(f"No {result['combo']} signals found in the backtest period.")
        return

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Signals", result['total_signals'])
    c2.metric("Win Rate (5d)", f"{result['win_rate_5d']:.1f}%")
    c3.metric("Avg Return (5d)", f"{result['avg_return_5d']:+.2f}%")
    c4.metric("Avg Return (20d)", f"{result['avg_return_20d']:+.2f}%")

    # Performance by holding period
    st.markdown("### Performance by Holding Period")
    perf = pd.DataFrame({
        'Holding Period': ['5 days', '10 days', '20 days'],
        'Win Rate (%)': [result['win_rate_5d'], result['win_rate_10d'], result['win_rate_20d']],
        'Avg Return (%)': [result['avg_return_5d'], result['avg_return_10d'], result['avg_return_20d']],
    })
    st.dataframe(perf, use_container_width=True, hide_index=True)

    # Equity curve
    trades = result['trades']
    if trades:
        st.markdown("### Equity Curve (5-day holding)")
        cum = []
        running = 0.0
        for t in trades:
            running += t['return_5d']
            cum.append(running)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(1, len(cum) + 1)),
            y=cum,
            mode='lines+markers',
            name='Cumulative Return',
            line=dict(color='#2196F3', width=2),
            marker=dict(size=5),
        ))
        fig.add_hline(y=0, line_dash='dash', line_color='grey')
        fig.update_layout(
            xaxis_title='Trade #',
            yaxis_title='Cumulative Return (%)',
            template='plotly_dark',
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Trade list
    st.markdown("### Individual Trades")
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        def _color_return(val):
            try:
                v = float(val)
                if v > 0:
                    return 'color: #4caf50'
                elif v < 0:
                    return 'color: #ef5350'
            except (ValueError, TypeError):
                pass
            return ''

        st.dataframe(
            trades_df.style.map(_color_return,
                                 subset=['return_5d', 'return_10d', 'return_20d']),
            use_container_width=True,
            hide_index=True,
        )


def _display_batch(results: list, combo: str):
    st.subheader(f"Batch Results: {combo}")

    if not results:
        st.warning(f"No {combo} signals found across any stocks.")
        return

    total_signals = sum(r['total_signals'] for r in results)
    if total_signals == 0:
        st.warning("Zero total signals.")
        return

    # Weighted averages
    def _wavg(key):
        return sum(r[key] * r['total_signals'] for r in results) / total_signals

    avg_wr5 = _wavg('win_rate_5d')
    avg_wr10 = _wavg('win_rate_10d')
    avg_wr20 = _wavg('win_rate_20d')
    avg_r5 = _wavg('avg_return_5d')
    avg_r10 = _wavg('avg_return_10d')
    avg_r20 = _wavg('avg_return_20d')

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stocks with Signals", len(results))
    c2.metric("Total Signals", total_signals)
    c3.metric("Avg Win Rate (5d)", f"{avg_wr5:.1f}%")
    c4.metric("Avg Return (5d)", f"{avg_r5:+.2f}%")

    # Aggregate performance
    st.markdown("### Aggregate Performance")
    agg = pd.DataFrame({
        'Holding Period': ['5 days', '10 days', '20 days'],
        'Win Rate (%)': [round(avg_wr5, 1), round(avg_wr10, 1), round(avg_wr20, 1)],
        'Avg Return (%)': [round(avg_r5, 2), round(avg_r10, 2), round(avg_r20, 2)],
    })
    st.dataframe(agg, use_container_width=True, hide_index=True)

    # Stock-by-stock
    st.markdown("### Stock-by-Stock Results")
    rows = []
    for r in results:
        rows.append({
            'Symbol': r['symbol'],
            'Signals': r['total_signals'],
            'Win Rate 5d (%)': r['win_rate_5d'],
            'Avg Ret 5d (%)': r['avg_return_5d'],
            'Win Rate 20d (%)': r['win_rate_20d'],
            'Avg Ret 20d (%)': r['avg_return_20d'],
        })
    stock_df = pd.DataFrame(rows).sort_values('Avg Ret 5d (%)', ascending=False)

    def _color_val(val):
        try:
            v = float(val)
            if v > 0:
                return 'color: #4caf50'
            elif v < 0:
                return 'color: #ef5350'
        except (ValueError, TypeError):
            pass
        return ''

    st.dataframe(
        stock_df.style.map(_color_val,
                            subset=['Avg Ret 5d (%)', 'Avg Ret 20d (%)']),
        use_container_width=True,
        hide_index=True,
    )
