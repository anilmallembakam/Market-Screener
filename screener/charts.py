import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Optional


def candlestick_chart(df: pd.DataFrame, symbol: str,
                      overlays: Optional[List[str]] = None,
                      support_levels: Optional[List[float]] = None,
                      resistance_levels: Optional[List[float]] = None,
                      show_volume: bool = True,
                      show_rsi: bool = True) -> go.Figure:
    num_rows = 1 + int(show_volume) + int(show_rsi)
    heights = [0.6]
    subtitles = [symbol]
    if show_volume:
        heights.append(0.2)
        subtitles.append('Volume')
    if show_rsi:
        heights.append(0.2)
        subtitles.append('RSI')

    fig = make_subplots(rows=num_rows, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=heights,
                        subplot_titles=subtitles)

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name='OHLC',
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350',
    ), row=1, col=1)

    # Overlay lines
    colors_map = {
        'EMA_20': '#2196F3', 'EMA_50': '#FF9800', 'EMA_200': '#F44336',
        'BB_Upper': '#9E9E9E', 'BB_Lower': '#9E9E9E', 'BB_Middle': '#BDBDBD',
        'VWAP': '#AB47BC',
    }
    if overlays:
        for col in overlays:
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col], name=col,
                    line=dict(color=colors_map.get(col, '#FFFFFF'), width=1),
                ), row=1, col=1)

    # S/R levels
    if support_levels:
        for level in support_levels:
            fig.add_hline(y=level, line_dash="dash", line_color="#4CAF50",
                          annotation_text=f"S: {level:.2f}", row=1, col=1)
    if resistance_levels:
        for level in resistance_levels:
            fig.add_hline(y=level, line_dash="dash", line_color="#F44336",
                          annotation_text=f"R: {level:.2f}", row=1, col=1)

    current_row = 2

    # Volume
    if show_volume:
        vol_colors = ['#ef5350' if df['Close'].iloc[i] < df['Open'].iloc[i]
                      else '#26a69a' for i in range(len(df))]
        fig.add_trace(go.Bar(
            x=df.index, y=df['Volume'], name='Volume',
            marker_color=vol_colors, showlegend=False,
        ), row=current_row, col=1)
        current_row += 1

    # RSI
    if show_rsi and 'RSI' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['RSI'], name='RSI',
            line=dict(color='#AB47BC', width=1.5),
        ), row=current_row, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#F44336",
                      row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#4CAF50",
                      row=current_row, col=1)
        fig.add_hrect(y0=30, y1=70, fillcolor="gray", opacity=0.1,
                      row=current_row, col=1)

    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        template='plotly_dark',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=20, t=60, b=30),
    )
    return fig


def oi_chart(calls: pd.DataFrame, puts: pd.DataFrame, current_price: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=calls['strike'], y=calls['openInterest'].fillna(0),
        name='Call OI', marker_color='#26a69a',
    ))
    fig.add_trace(go.Bar(
        x=puts['strike'], y=puts['openInterest'].fillna(0),
        name='Put OI', marker_color='#ef5350',
    ))
    fig.add_vline(x=current_price, line_dash="dash", line_color="white",
                  annotation_text=f"Spot: {current_price:.2f}")
    fig.update_layout(
        barmode='group',
        title='Open Interest Distribution',
        template='plotly_dark',
        height=400,
        xaxis_title='Strike Price',
        yaxis_title='Open Interest',
    )
    return fig


def iv_smile_chart(calls: pd.DataFrame, puts: pd.DataFrame, current_price: float) -> go.Figure:
    fig = go.Figure()
    calls_sorted = calls.sort_values('strike')
    puts_sorted = puts.sort_values('strike')

    fig.add_trace(go.Scatter(
        x=calls_sorted['strike'], y=calls_sorted['impliedVolatility'] * 100,
        name='Call IV', mode='lines+markers',
        line=dict(color='#26a69a'),
    ))
    fig.add_trace(go.Scatter(
        x=puts_sorted['strike'], y=puts_sorted['impliedVolatility'] * 100,
        name='Put IV', mode='lines+markers',
        line=dict(color='#ef5350'),
    ))
    fig.add_vline(x=current_price, line_dash="dash", line_color="white",
                  annotation_text=f"Spot: {current_price:.2f}")
    fig.update_layout(
        title='IV Smile',
        template='plotly_dark',
        height=400,
        xaxis_title='Strike Price',
        yaxis_title='Implied Volatility (%)',
    )
    return fig
