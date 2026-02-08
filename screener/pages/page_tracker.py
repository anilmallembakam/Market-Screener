"""Performance Tracker page - Track historical alerts and their performance."""
import streamlit as st
import pandas as pd
from typing import Dict
from datetime import datetime, timedelta
from screener.alert_history import (
    get_historical_alerts,
    fetch_performance_data,
    calculate_performance,
    clear_old_alerts,
    delete_alert,
    get_alerts_by_date,
    get_available_dates,
    get_weekly_summary,
)
from screener.scheduler import (
    run_all_markets_auto_save,
    get_last_auto_save_times,
    is_market_closed,
)


def _safe_market(val) -> str:
    """Safely get market value as uppercase string."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 'US'
    return str(val).upper()


def render(daily_data: Dict[str, pd.DataFrame], market: str = 'us'):
    st.header("📊 Performance Tracker")

    # Sub-tabs for different views
    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
        "📈 Live Tracker",
        "📅 Calendar View",
        "📊 Weekly Summary",
        "🔍 Winner Analytics"
    ])

    with sub_tab1:
        _render_live_tracker(daily_data, market)

    with sub_tab2:
        _render_calendar_view(market)

    with sub_tab3:
        _render_weekly_summary(market)

    with sub_tab4:
        _render_winner_analytics(market)


def _render_live_tracker(daily_data: Dict[str, pd.DataFrame], market: str):
    """Main tracker view with filters and auto-save."""
    st.caption("Track how your alerted stocks perform over 5-20 days")

    # Auto-save section
    with st.expander("🤖 Auto-Save Settings", expanded=False):
        st.caption("Auto-save only includes alerts with **Score ≥ 5**")

        col1, col2, col3 = st.columns(3)

        last_saves = get_last_auto_save_times()

        with col1:
            st.markdown("**🇺🇸 US Market**")
            us_status = "✅ Closed" if is_market_closed('us') else "🔴 Open"
            st.caption(f"Status: {us_status}")
            st.caption(f"Last auto-save: {last_saves.get('us', 'Never')}")

        with col2:
            st.markdown("**🇮🇳 Indian Market**")
            in_status = "✅ Closed" if is_market_closed('indian') else "🔴 Open"
            st.caption(f"Status: {in_status}")
            st.caption(f"Last auto-save: {last_saves.get('indian', 'Never')}")

        with col3:
            if st.button("🔄 Run Auto-Save Now", help="Manually trigger auto-save for closed markets (Score ≥ 5)"):
                with st.spinner("Running auto-save..."):
                    results = run_all_markets_auto_save()
                    for mkt, count in results.items():
                        if count > 0:
                            st.success(f"{mkt.upper()}: Saved {count} alerts (Score ≥ 5)")
                        else:
                            st.info(f"{mkt.upper()}: No new alerts or market not closed")

    # Main filters row
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
    with col1:
        market_filter = st.selectbox(
            "Market",
            ['All', 'US', 'Indian'],
            index=1 if market == 'us' else 2,
            key='tracker_market'
        )
    with col2:
        direction_filter = st.selectbox(
            "Direction",
            ['All', 'Bullish', 'Bearish'],
            index=0,
            key='tracker_direction'
        )
    with col3:
        setup_filter = st.selectbox(
            "Setup",
            ['All', 'Bull Call Spread', 'Bear Put Spread', 'Iron Condor', 'Long Straddle', 'Calendar Spread'],
            index=0,
            key='tracker_setup'
        )
    with col4:
        days_back = st.selectbox("Show alerts from last", [7, 14, 30, 60], index=2, key='tracker_days')
    with col5:
        track_days = st.selectbox("Track performance for", [5, 10, 15, 20], index=3, key='tracker_track')

    # Clear old alerts button
    col_clear, _ = st.columns([1, 3])
    with col_clear:
        if st.button("🗑️ Clear alerts older than 60 days"):
            removed = clear_old_alerts(60)
            st.success(f"Removed {removed} old alerts")

    # Convert filter values for query
    market_query = None if market_filter == 'All' else market_filter.lower()
    direction_query = None if direction_filter == 'All' else direction_filter
    setup_query = None if setup_filter == 'All' else setup_filter

    # Load historical alerts with filters
    alerts_df = get_historical_alerts(days_back, market=market_query, direction=direction_query)

    # Filter by setup if specified
    if setup_query and not alerts_df.empty:
        alerts_df = alerts_df[alerts_df['combo'].str.contains(setup_query, case=False, na=False)]

    if alerts_df.empty:
        st.info("No historical alerts found. Save alerts from the Alerts tab or use Auto-Save.")
        st.markdown("""
        **How it works:**
        1. Go to the **Alerts/Summary** tab and click **Save Alerts to History**
        2. Or enable **Auto-Save** to automatically save alerts after market close
        3. Come back here to track their performance over time
        """)
        return

    st.markdown(f"**{len(alerts_df)} alerts found** from the last {days_back} days")

    # Calculate performance for each alert
    performance_data = []

    with st.spinner("Calculating performance..."):
        for _, alert in alerts_df.iterrows():
            symbol = alert['symbol']
            alert_date = alert['date']

            price_data = fetch_performance_data(symbol, alert_date, track_days)
            perf = calculate_performance(alert.to_dict(), price_data)

            performance_data.append({
                'Symbol': symbol,
                'Market': _safe_market(alert.get('market', 'us')),
                'Alert Date': alert_date,
                'Direction': alert.get('direction', 'N/A'),
                'Score': alert.get('score', 0),
                'Setup': alert.get('combo', 'N/A'),
                'Alert Price': alert.get('alert_price', 0),
                'Current Price': perf['current_price'],
                'P&L %': perf['pnl_pct'],
                'Max Gain %': perf['max_gain_pct'],
                'Max DD %': perf['max_drawdown_pct'],
                'Days': perf['days_tracked'],
                'Status': perf['status'],
                'Momentum': perf['momentum'],
            })

    perf_df = pd.DataFrame(performance_data)

    if perf_df.empty:
        st.warning("Could not calculate performance data")
        return

    # Summary metrics
    _render_summary_metrics(perf_df)

    # Filter options for table
    st.subheader("Alerts Performance")
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.multiselect(
            "Filter by Status",
            ['Winner', 'Gaining', 'Flat', 'Slight Loss', 'Loser'],
            default=[],
            key='status_filter'
        )
    with col2:
        momentum_filter = st.multiselect(
            "Filter by Momentum",
            ['Strong', 'Stable', 'Slowing', 'Losing Steam', 'Too Early'],
            default=[],
            key='momentum_filter'
        )

    # Apply filters
    filtered_df = perf_df.copy()
    if status_filter:
        filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]
    if momentum_filter:
        filtered_df = filtered_df[filtered_df['Momentum'].isin(momentum_filter)]

    # Display table with styling
    _render_performance_table(filtered_df)

    # Alerts losing steam section
    losing_steam_df = perf_df[perf_df['Momentum'] == 'Losing Steam']
    if not losing_steam_df.empty:
        st.subheader("⚠️ Alerts Losing Steam")
        st.warning(f"{len(losing_steam_df)} alerts are showing weakening momentum - consider exiting")
        st.dataframe(
            losing_steam_df[['Symbol', 'Market', 'Alert Date', 'Direction', 'Setup', 'P&L %', 'Max Gain %', 'Days']],
            use_container_width=True,
            hide_index=True,
        )

    # Top and bottom performers side by side
    col_top, col_bottom = st.columns(2)

    with col_top:
        top_df = perf_df.nlargest(5, 'P&L %')
        if not top_df.empty:
            st.subheader("🏆 Top 5 Performers")
            st.dataframe(
                top_df[['Symbol', 'Market', 'Direction', 'Setup', 'P&L %', 'Max Gain %', 'Status']],
                use_container_width=True,
                hide_index=True,
            )

    with col_bottom:
        bottom_df = perf_df.nsmallest(5, 'P&L %')
        if not bottom_df.empty:
            st.subheader("📉 Bottom 5 Performers")
            st.dataframe(
                bottom_df[['Symbol', 'Market', 'Direction', 'Setup', 'P&L %', 'Max DD %', 'Status']],
                use_container_width=True,
                hide_index=True,
            )


def _render_calendar_view(market: str):
    """Calendar-based historical view of alerts."""
    st.caption("View alerts from any date and see their performance till today")

    # Get available dates
    available_dates = get_available_dates()

    if not available_dates:
        st.info("No historical alerts found. Save some alerts first!")
        return

    col1, col2 = st.columns([1, 1])

    with col1:
        # Date selector
        min_date = datetime.strptime(min(available_dates), '%Y-%m-%d').date()
        max_date = datetime.strptime(max(available_dates), '%Y-%m-%d').date()

        selected_date = st.date_input(
            "Select Alert Date",
            value=datetime.strptime(available_dates[0], '%Y-%m-%d').date(),
            min_value=min_date,
            max_value=max_date,
            key='calendar_date'
        )

    with col2:
        market_filter = st.selectbox(
            "Market",
            ['All', 'US', 'Indian'],
            index=0,
            key='calendar_market'
        )

    date_str = selected_date.strftime('%Y-%m-%d')
    market_query = None if market_filter == 'All' else market_filter.lower()

    # Check if this date has alerts
    if date_str not in available_dates:
        st.warning(f"No alerts found for {date_str}. Try selecting a different date.")
        st.markdown("**Dates with alerts:**")
        for d in available_dates[:10]:
            st.caption(f"• {d}")
        return

    # Get alerts for selected date
    alerts_df = get_alerts_by_date(date_str, market_query)

    if alerts_df.empty:
        st.info(f"No alerts for {date_str} in {market_filter} market")
        return

    # Calculate days since alert
    days_since = (datetime.now() - datetime.strptime(date_str, '%Y-%m-%d')).days

    st.markdown(f"### Alerts from {date_str}")
    st.caption(f"**{len(alerts_df)} alerts** | Tracking for **{days_since} days**")

    # Calculate performance till today
    performance_data = []

    with st.spinner("Calculating performance..."):
        for _, alert in alerts_df.iterrows():
            symbol = alert['symbol']
            price_data = fetch_performance_data(symbol, date_str, days_since)
            perf = calculate_performance(alert.to_dict(), price_data)

            performance_data.append({
                'Symbol': symbol,
                'Market': _safe_market(alert.get('market', 'us')),
                'Direction': alert.get('direction', 'N/A'),
                'Score': alert.get('score', 0),
                'Alert Price': alert.get('alert_price', 0),
                'Current Price': perf['current_price'],
                'P&L %': perf['pnl_pct'],
                'Max Gain %': perf['max_gain_pct'],
                'Max DD %': perf['max_drawdown_pct'],
                'Days': perf['days_tracked'],
                'Status': perf['status'],
                'Momentum': perf['momentum'],
            })

    perf_df = pd.DataFrame(performance_data)

    if not perf_df.empty:
        # Summary for this date
        _render_summary_metrics(perf_df)

        # Performance table
        _render_performance_table(perf_df)


def _render_weekly_summary(market: str):
    """Weekly performance summary report."""
    st.caption("End-of-week performance report on your alerts")

    col1, col2 = st.columns([1, 2])

    with col1:
        weeks_back = st.selectbox(
            "Report Period",
            [1, 2, 4, 8],
            index=0,
            format_func=lambda x: f"Last {x} week{'s' if x > 1 else ''}",
            key='weekly_weeks'
        )

    with col2:
        market_filter = st.selectbox(
            "Market",
            ['All', 'US', 'Indian'],
            index=0,
            key='weekly_market'
        )

    market_query = None if market_filter == 'All' else market_filter.lower()

    with st.spinner("Generating weekly summary..."):
        summary = get_weekly_summary(weeks_back, market_query)

    if summary['total_alerts'] == 0:
        st.info(f"No alerts found in the last {weeks_back} week(s)")
        return

    # Header
    st.markdown(f"### Weekly Report: {summary['period_start']} to {summary['period_end']}")

    # Main metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Alerts", summary['total_alerts'])
    with col2:
        st.metric("Winners (>5%)", summary['winners'],
                  delta=f"{summary['win_rate']}% win rate")
    with col3:
        st.metric("Losers (<-5%)", summary['losers'],
                  delta_color="inverse")
    with col4:
        delta_color = "normal" if summary['avg_pnl'] >= 0 else "inverse"
        st.metric("Avg P&L", f"{summary['avg_pnl']}%",
                  delta="Profitable" if summary['avg_pnl'] > 0 else "Losing")
    with col5:
        st.metric("Losing Steam", summary['losing_steam_count'],
                  delta="Watch!" if summary['losing_steam_count'] > 0 else None,
                  delta_color="off")

    st.markdown("---")

    # Performance by Direction
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📊 By Direction")
        if summary['by_direction']:
            for direction, stats in summary['by_direction'].items():
                emoji = "🟢" if direction == "Bullish" else "🔴"
                st.markdown(f"""
                **{emoji} {direction}**
                - Alerts: {stats['count']}
                - Avg P&L: {stats['avg_pnl']}%
                - Win Rate: {stats['win_rate']}%
                """)
        else:
            st.caption("No data")

    with col2:
        st.markdown("#### 🌍 By Market")
        if summary['by_market']:
            for mkt, stats in summary['by_market'].items():
                flag = "🇺🇸" if mkt == "US" else "🇮🇳"
                st.markdown(f"""
                **{flag} {mkt}**
                - Alerts: {stats['count']}
                - Avg P&L: {stats['avg_pnl']}%
                - Win Rate: {stats['win_rate']}%
                """)
        else:
            st.caption("No data")

    st.markdown("---")

    # Best and Worst performers
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🏆 Best Performer")
        if summary['best_performer']:
            best = summary['best_performer']
            st.success(f"""
            **{best['symbol']}**
            - P&L: +{best['pnl_pct']}%
            - Max Gain: {best['max_gain_pct']}%
            - Direction: {best['direction']}
            """)
        else:
            st.caption("No data")

    with col2:
        st.markdown("#### 📉 Worst Performer")
        if summary['worst_performer']:
            worst = summary['worst_performer']
            st.error(f"""
            **{worst['symbol']}**
            - P&L: {worst['pnl_pct']}%
            - Max DD: {worst['max_drawdown_pct']}%
            - Direction: {worst['direction']}
            """)
        else:
            st.caption("No data")


def _render_summary_metrics(perf_df: pd.DataFrame):
    """Render summary metrics row."""
    st.subheader("Summary")
    col1, col2, col3, col4, col5 = st.columns(5)

    winners = len(perf_df[perf_df['P&L %'] >= 5])
    losers = len(perf_df[perf_df['P&L %'] <= -5])
    flat = len(perf_df) - winners - losers
    avg_pnl = perf_df['P&L %'].mean()
    losing_steam = len(perf_df[perf_df['Momentum'] == 'Losing Steam'])

    with col1:
        st.metric("Winners (>5%)", winners, delta=f"{winners/len(perf_df)*100:.0f}%")
    with col2:
        st.metric("Losers (<-5%)", losers, delta=f"-{losers/len(perf_df)*100:.0f}%", delta_color="inverse")
    with col3:
        st.metric("Flat", flat)
    with col4:
        st.metric("Avg P&L", f"{avg_pnl:.1f}%", delta="Good" if avg_pnl > 0 else "Bad")
    with col5:
        st.metric("Losing Steam", losing_steam, delta="Watch" if losing_steam > 0 else None, delta_color="off")


def _render_performance_table(perf_df: pd.DataFrame):
    """Render styled performance dataframe."""
    # Style functions
    def color_pnl(val):
        if val >= 5:
            return 'background-color: #1b5e20; color: white'
        elif val >= 0:
            return 'background-color: #2e7d32; color: white'
        elif val >= -5:
            return 'background-color: #ff8f00; color: black'
        else:
            return 'background-color: #b71c1c; color: white'

    def color_momentum(val):
        if val == 'Strong':
            return 'background-color: #1b5e20; color: white'
        elif val == 'Stable':
            return 'background-color: #2e7d32; color: white'
        elif val == 'Slowing':
            return 'background-color: #ff8f00; color: black'
        elif val == 'Losing Steam':
            return 'background-color: #b71c1c; color: white'
        return ''

    st.dataframe(
        perf_df.style
            .applymap(color_pnl, subset=['P&L %'])
            .applymap(color_momentum, subset=['Momentum']),
        use_container_width=True,
        hide_index=True,
        column_config={
            'Alert Price': st.column_config.NumberColumn('Alert $', format="%.2f"),
            'Current Price': st.column_config.NumberColumn('Current $', format="%.2f"),
            'P&L %': st.column_config.NumberColumn('P&L %', format="%.1f%%"),
            'Max Gain %': st.column_config.NumberColumn('Max Gain', format="%.1f%%"),
            'Max DD %': st.column_config.NumberColumn('Max DD', format="%.1f%%"),
        }
    )


def _render_winner_analytics(market: str):
    """Analyze common factors among winning alerts."""
    st.caption("Discover what makes alerts successful - find common patterns among winners")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        days_back = st.selectbox("Analyze alerts from last", [14, 30, 60, 90], index=1, key='analytics_days')
    with col2:
        min_pnl = st.selectbox("Winner threshold (P&L %)", [3, 5, 10, 15], index=1, key='analytics_pnl')
    with col3:
        market_filter = st.selectbox("Market", ['All', 'US', 'Indian'], index=0, key='analytics_market')

    market_query = None if market_filter == 'All' else market_filter.lower()

    # Get all alerts
    alerts_df = get_historical_alerts(days_back, market=market_query)

    if alerts_df.empty:
        st.info("No alerts found for analysis. Save more alerts first!")
        return

    # Calculate performance for all alerts
    all_performance = []

    with st.spinner("Analyzing alerts..."):
        for _, alert in alerts_df.iterrows():
            price_data = fetch_performance_data(alert['symbol'], alert['date'], 20)
            perf = calculate_performance(alert.to_dict(), price_data)

            all_performance.append({
                'symbol': alert['symbol'],
                'date': alert['date'],
                'direction': alert.get('direction', 'N/A'),
                'score': alert.get('score', 0),
                'criteria': alert.get('criteria', ''),
                'pattern': alert.get('pattern', ''),
                'combo': alert.get('combo', ''),
                'market': _safe_market(alert.get('market', 'us')),
                'pnl_pct': perf['pnl_pct'],
                'max_gain_pct': perf['max_gain_pct'],
                'status': perf['status'],
            })

    perf_df = pd.DataFrame(all_performance)

    if perf_df.empty:
        st.warning("Could not calculate performance data")
        return

    # Split into winners and losers
    winners_df = perf_df[perf_df['pnl_pct'] >= min_pnl]
    losers_df = perf_df[perf_df['pnl_pct'] <= -min_pnl]
    total = len(perf_df)

    # Summary
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Alerts", total)
    with col2:
        st.metric("Winners", len(winners_df), delta=f"{len(winners_df)/total*100:.0f}%")
    with col3:
        st.metric("Losers", len(losers_df), delta=f"-{len(losers_df)/total*100:.0f}%", delta_color="inverse")
    with col4:
        avg_winner = winners_df['pnl_pct'].mean() if not winners_df.empty else 0
        st.metric("Avg Winner P&L", f"{avg_winner:.1f}%")

    if winners_df.empty:
        st.warning(f"No winners found with P&L >= {min_pnl}%. Try lowering the threshold.")
        return

    st.markdown("---")
    st.subheader("🔍 What Makes Winners Win?")

    # Analysis columns
    col1, col2 = st.columns(2)

    with col1:
        # Score Distribution
        st.markdown("#### 📊 Score Distribution")
        score_analysis = winners_df.groupby('score').agg({
            'symbol': 'count',
            'pnl_pct': 'mean'
        }).rename(columns={'symbol': 'Count', 'pnl_pct': 'Avg P&L %'}).round(1)
        score_analysis = score_analysis.sort_index(ascending=False)

        if not score_analysis.empty:
            best_score = score_analysis['Avg P&L %'].idxmax()
            st.success(f"**Best performing score: {best_score}** (Avg P&L: {score_analysis.loc[best_score, 'Avg P&L %']:.1f}%)")
            st.dataframe(score_analysis, use_container_width=True)

    with col2:
        # Direction Analysis
        st.markdown("#### 🎯 Direction Analysis")
        dir_winners = winners_df.groupby('direction').agg({
            'symbol': 'count',
            'pnl_pct': 'mean'
        }).rename(columns={'symbol': 'Winners', 'pnl_pct': 'Avg P&L %'}).round(1)

        dir_all = perf_df.groupby('direction').size().rename('Total')
        dir_analysis = dir_winners.join(dir_all)
        dir_analysis['Win Rate %'] = (dir_analysis['Winners'] / dir_analysis['Total'] * 100).round(1)

        if not dir_analysis.empty:
            best_dir = dir_analysis['Win Rate %'].idxmax()
            st.success(f"**Best direction: {best_dir}** (Win Rate: {dir_analysis.loc[best_dir, 'Win Rate %']:.0f}%)")
            st.dataframe(dir_analysis[['Winners', 'Total', 'Win Rate %', 'Avg P&L %']], use_container_width=True)

    st.markdown("---")

    # Pattern Analysis
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📈 Winning Patterns")
        # Extract patterns from winners
        pattern_counts = {}
        for patterns in winners_df['pattern'].dropna():
            if patterns and str(patterns) != 'nan':
                for p in str(patterns).split(','):
                    p = p.strip()
                    if p:
                        pattern_counts[p] = pattern_counts.get(p, 0) + 1

        if pattern_counts:
            pattern_df = pd.DataFrame([
                {'Pattern': k, 'Count': v, 'Win %': round(v / len(winners_df) * 100, 1)}
                for k, v in sorted(pattern_counts.items(), key=lambda x: -x[1])[:10]
            ])
            st.success(f"**Top pattern: {pattern_df.iloc[0]['Pattern']}** ({pattern_df.iloc[0]['Count']} winners)")
            st.dataframe(pattern_df, use_container_width=True, hide_index=True)
        else:
            st.info("No pattern data available")

    with col2:
        st.markdown("#### 🎲 Winning Setups (Combo)")
        # Extract combos from winners
        combo_counts = {}
        for combo in winners_df['combo'].dropna():
            if combo and str(combo) != 'nan' and str(combo) != 'No clear setup':
                combo = str(combo).strip()
                if combo:
                    combo_counts[combo] = combo_counts.get(combo, 0) + 1

        if combo_counts:
            combo_df = pd.DataFrame([
                {'Setup': k, 'Count': v, 'Win %': round(v / len(winners_df) * 100, 1)}
                for k, v in sorted(combo_counts.items(), key=lambda x: -x[1])[:10]
            ])
            st.success(f"**Top setup: {combo_df.iloc[0]['Setup']}** ({combo_df.iloc[0]['Count']} winners)")
            st.dataframe(combo_df, use_container_width=True, hide_index=True)
        else:
            st.info("No setup/combo data available")

    st.markdown("---")

    # Criteria Analysis
    st.markdown("#### 🔑 Key Criteria in Winners")
    criteria_counts = {}
    for criteria in winners_df['criteria'].dropna():
        if criteria and str(criteria) != 'nan':
            for c in str(criteria).split(','):
                c = c.strip()
                if c:
                    criteria_counts[c] = criteria_counts.get(c, 0) + 1

    if criteria_counts:
        # Sort and get top 15
        top_criteria = sorted(criteria_counts.items(), key=lambda x: -x[1])[:15]
        criteria_df = pd.DataFrame([
            {'Criteria': k, 'Appearances': v, '% of Winners': round(v / len(winners_df) * 100, 1)}
            for k, v in top_criteria
        ])

        st.success(f"**Most common criteria: {criteria_df.iloc[0]['Criteria']}** (in {criteria_df.iloc[0]['% of Winners']:.0f}% of winners)")

        # Display as bar chart
        st.bar_chart(criteria_df.set_index('Criteria')['Appearances'])
        st.dataframe(criteria_df, use_container_width=True, hide_index=True)
    else:
        st.info("No criteria data available")

    st.markdown("---")

    # Winners vs Losers Comparison
    st.markdown("#### ⚔️ Winners vs Losers Comparison")

    if not losers_df.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Winners Profile**")
            st.markdown(f"""
            - Avg Score: **{winners_df['score'].mean():.1f}**
            - Avg P&L: **+{winners_df['pnl_pct'].mean():.1f}%**
            - Avg Max Gain: **{winners_df['max_gain_pct'].mean():.1f}%**
            - Most Common Direction: **{winners_df['direction'].mode().iloc[0] if not winners_df['direction'].mode().empty else 'N/A'}**
            """)

        with col2:
            st.markdown("**Losers Profile**")
            st.markdown(f"""
            - Avg Score: **{losers_df['score'].mean():.1f}**
            - Avg P&L: **{losers_df['pnl_pct'].mean():.1f}%**
            - Avg Max Gain: **{losers_df['max_gain_pct'].mean():.1f}%**
            - Most Common Direction: **{losers_df['direction'].mode().iloc[0] if not losers_df['direction'].mode().empty else 'N/A'}**
            """)

        # Score comparison
        st.markdown("**Score Comparison**")
        comparison_data = {
            'Metric': ['Avg Score', 'Score 5', 'Score 6', 'Score 7', 'Score 8+'],
            'Winners': [
                round(winners_df['score'].mean(), 1),
                len(winners_df[winners_df['score'] == 5]),
                len(winners_df[winners_df['score'] == 6]),
                len(winners_df[winners_df['score'] == 7]),
                len(winners_df[winners_df['score'] >= 8]),
            ],
            'Losers': [
                round(losers_df['score'].mean(), 1),
                len(losers_df[losers_df['score'] == 5]),
                len(losers_df[losers_df['score'] == 6]),
                len(losers_df[losers_df['score'] == 7]),
                len(losers_df[losers_df['score'] >= 8]),
            ],
        }
        st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)
    else:
        st.info(f"No losers with P&L <= -{min_pnl}% found for comparison")

    # Top Winners List
    st.markdown("---")
    st.markdown("#### 🏆 Top 10 Winners")
    top_winners = winners_df.nlargest(10, 'pnl_pct')[['symbol', 'date', 'direction', 'score', 'pattern', 'combo', 'pnl_pct']]
    top_winners.columns = ['Symbol', 'Date', 'Direction', 'Score', 'Pattern', 'Setup', 'P&L %']
    st.dataframe(top_winners, use_container_width=True, hide_index=True)
