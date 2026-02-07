import streamlit as st


def render():
    """Render educational guide - technical indicators, patterns, and trading strategies."""
    st.header("Trading Guide & Educational Resources")
    st.markdown(
        "Learn how to use this screener effectively, understand the technical "
        "indicators and candlestick patterns, and discover **proven trading "
        "combinations** that work in real markets."
    )

    _render_quick_start()
    st.markdown("---")
    _render_technical_indicators()
    st.markdown("---")
    _render_candlestick_patterns()
    st.markdown("---")
    _render_trading_combinations()
    st.markdown("---")
    _render_scoring_system()
    st.markdown("---")
    _render_quick_reference()


# ── Section 1 ──────────────────────────────────────────────────────────────
def _render_quick_start():
    st.subheader("Quick Start - How to Use This Screener")
    st.info(
        "**Recommended Daily Workflow:**\n\n"
        "1. **Check Market Mood** (top panel) -- Is the market bullish, bearish, or neutral?\n"
        "2. **Scan Alerts** (tab 1) -- Find stocks with high confluence scores (5+ is strong)\n"
        "3. **Verify Technicals** (tab 3) -- Drill into individual indicator values\n"
        "4. **Check Chart** (tab 8) -- Visually confirm price action and patterns\n"
        "5. **Trade Signals** (tab 7) -- For index option strategies (Nifty / BankNifty)\n\n"
        "**Tab Guide:**\n"
        "- **Alerts/Summary** -- Start here. Stocks ranked by multi-factor score\n"
        "- **Pattern Scanner** -- Hunt for specific candlestick patterns across all stocks\n"
        "- **Technicals** -- Deep-dive into RSI, MACD, EMA, BB, ADX for each stock\n"
        "- **Breakouts** -- Stocks breaking out of consolidation ranges\n"
        "- **S/R Levels** -- Support & resistance zones on chart\n"
        "- **F&O Data** -- Options chain, PCR, Max Pain, OI analysis\n"
        "- **Trade Signals** -- Strategy recommendations + strike details for index options\n"
        "- **Chart** -- Interactive chart with indicator overlays"
    )


# ── Section 2 ──────────────────────────────────────────────────────────────
def _render_technical_indicators():
    st.subheader("Technical Indicators Reference")

    # ── Trend Indicators ──
    with st.expander("Trend Indicators (EMA, MACD, ADX)", expanded=False):
        st.markdown("""
### EMA - Exponential Moving Average (20, 50, 200)

**What it is:** A weighted moving average giving more importance to recent prices.

**How to read:**
- Price **above** EMA = Bullish bias
- Price **below** EMA = Bearish bias
- **EMA Alignment:** 20 > 50 > 200 = Strong uptrend
- **Reverse Alignment:** 20 < 50 < 200 = Strong downtrend

**Best use cases:**
- Identify trend direction and dynamic support/resistance
- Enter on pullbacks to EMA20 in a strong uptrend
- EMA crossovers (20 crossing 50) signal trend changes

**Common mistakes:**
- Using in choppy / sideways markets (many false signals)
- Ignoring timeframe context (daily vs weekly)
- Not waiting for confirmation after an EMA cross

---

### MACD - Moving Average Convergence Divergence (12, 26, 9)

**What it is:** Momentum oscillator showing the relationship between two EMAs.

**How to read:**
- **Bullish Crossover:** MACD line crosses above signal line
- **Bearish Crossover:** MACD line crosses below signal line
- **Histogram:** Shows momentum strength
- **Divergence:** Price makes new high but MACD doesn't = bearish divergence (powerful signal)

**Best use cases:**
- Confirm trend reversals (crossover signals)
- Spot divergences (most reliable MACD signal)
- Momentum confirmation for breakout trades

**Common mistakes:**
- Trading every single crossover (many are false in ranging markets)
- Ignoring the overall trend context
- Not combining with price action

---

### ADX - Average Directional Index (14)

**What it is:** Measures trend **strength** on a 0-100 scale (NOT direction).

**How to read:**
- **ADX > 25:** Strong trend (use trend-following strategies)
- **ADX < 20:** Weak / no trend, ranging market (use mean reversion)
- **+DI > -DI:** Upward trend direction
- **-DI > +DI:** Downward trend direction
- **ADX rising:** Trend is getting stronger

**Best use cases:**
- Filter trending vs ranging markets before choosing strategy
- Confirm breakout validity (ADX should rise on real breakouts)
- Avoid trend strategies when ADX < 20

**Common mistakes:**
- Using ADX alone without direction indicators (+DI / -DI)
- Forgetting ADX is a lagging indicator
- Not switching strategy based on ADX level
""")

    # ── Oscillators ──
    with st.expander("Oscillators (RSI, Bollinger Bands)", expanded=False):
        st.markdown("""
### RSI - Relative Strength Index (14)

**What it is:** Momentum oscillator measuring speed and magnitude of price changes (0-100).

**How to read:**
- **RSI < 30:** Oversold (potential bounce)
- **RSI > 70:** Overbought (potential reversal)
- **RSI 30-70:** Neutral zone
- **Divergence:** Price makes new low but RSI doesn't = bullish divergence

**Best use cases:**
- Identify oversold / overbought conditions
- Divergence signals (very reliable)
- Confirm trend strength (RSI > 60 in uptrend is healthy)

**Common mistakes:**
- Blindly buying at RSI < 30 in strong downtrends (can stay oversold for weeks)
- Ignoring divergences (the most reliable RSI signal)
- Using same levels for all stocks (some stay > 70 for weeks in bull runs)

---

### Bollinger Bands (20, 2)

**What it is:** Volatility bands placed 2 standard deviations above / below a 20-period SMA.

**How to read:**
- **Price at lower band:** Potential oversold bounce
- **Price at upper band:** Potential overbought reversal
- **Band squeeze:** Low volatility, breakout likely coming
- **Band expansion:** High volatility, trend in progress

**Best use cases:**
- Mean reversion in ranging markets (buy lower band, sell upper band)
- Volatility measurement (band width)
- Breakout confirmation (price breaks band + expanding width)

**Common mistakes:**
- Fading strong trends (price can "walk the band" for weeks)
- Not waiting for reversal pattern confirmation at bands
- Ignoring the middle band (20 SMA acts as key support / resistance)
""")

    # ── Volume & Volatility ──
    with st.expander("Volume & Volatility (Volume Ratio, ATR, VWAP)", expanded=False):
        st.markdown("""
### Volume Ratio (vs 20-period SMA)

**What it is:** Current volume compared to 20-day average volume.

**How to read:**
- **Ratio > 1.5:** High volume (signals conviction behind the move)
- **Ratio < 0.5:** Low volume (weak move, likely to reverse)
- Volume confirmation is **essential** on breakouts

**Best use cases:**
- Confirm breakouts / breakdowns (must have volume spike)
- Validate reversals (high volume = institutional participation)
- Filter out low-conviction moves

**Common mistakes:**
- Ignoring volume on breakouts (most fail without volume)
- Not considering time of day for intraday analysis

---

### ATR - Average True Range (14)

**What it is:** Measures volatility by averaging the true range over 14 periods.

**How to read:**
- **High ATR:** Stock is volatile, wider stop-losses needed
- **Low ATR:** Stock is calm, tighter stops possible
- **Rising ATR:** Volatility increasing (trend may be starting or accelerating)

**Best use cases:**
- **Stop-loss placement:** Set stop at 1.5x ATR below entry
- **Position sizing:** Risk same rupee amount per stock regardless of price
- Identify volatility expansion (precedes big moves)

**Common mistakes:**
- Using fixed stop percentages instead of ATR-based stops
- Not adjusting position size when ATR changes
- Ignoring ATR when setting targets

---

### VWAP - Volume Weighted Average Price

**What it is:** Average price weighted by volume (primarily intraday).

**How to read:**
- **Price > VWAP:** Buyers in control (bullish bias)
- **Price < VWAP:** Sellers in control (bearish bias)
- **VWAP as magnet:** Price tends to revert to VWAP

**Best use cases:**
- Intraday fair value reference
- Institutional order flow gauge
- Mean reversion entries for day traders

**Common mistakes:**
- Using VWAP on daily / weekly charts (it is an intraday indicator)
- Not resetting VWAP each day
""")


# ── Section 3 ──────────────────────────────────────────────────────────────
def _render_candlestick_patterns():
    st.subheader("Candlestick Patterns Guide")
    st.markdown(
        "This screener detects **61 candlestick patterns** using TA-Lib. "
        "Below are the ~20 most **reliable and actionable** patterns grouped "
        "by type. Focus on these rather than memorising all 61."
    )

    # ── Strong Reversal ──
    with st.expander("Strong Reversal Patterns (High Reliability)", expanded=False):
        st.markdown("""
### Bullish Reversal

**Hammer** | Reliability: High
- Small body at top, long lower shadow (2-3x body), little/no upper shadow
- Appears after downtrend -- sellers pushed price down but buyers took control
- Best at support levels with volume confirmation

**Morning Star** | Reliability: Very High
- 3-candle pattern: Large red >> small indecision candle >> large green
- Strong reversal, especially if star gaps down
- Best after extended downtrend at major support

**Bullish Engulfing** | Reliability: High
- Green candle completely engulfs previous red candle's body
- Strong shift from selling to buying pressure
- Best after pullback in uptrend or at support

**Piercing Pattern** | Reliability: High
- 2-candle: Red candle followed by green closing above midpoint of red
- Shows aggressive buying after selling
- Best in downtrend at a support zone

**Three White Soldiers** | Reliability: Very High
- 3 consecutive green candles with higher closes, small/no wicks
- Very strong reversal (rare but powerful)
- Best after consolidation or downtrend

---

### Bearish Reversal

**Shooting Star** | Reliability: High
- Small body at bottom, long upper shadow, little/no lower shadow
- Buyers tried to push higher but sellers took control
- Best at resistance after uptrend

**Evening Star** | Reliability: Very High
- 3-candle: Large green >> small indecision >> large red
- Mirror of Morning Star
- Best after extended rally at resistance

**Bearish Engulfing** | Reliability: High
- Red candle completely engulfs previous green candle's body
- Strong shift from buying to selling
- Best at resistance in uptrend

**Dark Cloud Cover** | Reliability: High
- 2-candle: Green followed by red opening above but closing below midpoint
- Sellers dominated after initial strength
- Best at resistance after rally

**Three Black Crows** | Reliability: Very High
- 3 consecutive red candles with lower closes
- Strong bearish reversal (rare but powerful)
- Best after rally or consolidation
""")

    # ── Moderate Reversal ──
    with st.expander("Moderate Reversal Patterns (Needs Confirmation)", expanded=False):
        st.markdown("""
**Inverted Hammer** | Reliability: Moderate
- Small body at bottom, long upper wick (bullish after downtrend)
- Needs next-day confirmation (close above inverted hammer's high)

**Harami Pattern** | Reliability: Moderate
- Small candle inside previous large candle (pregnancy pattern)
- Signals indecision, potential reversal -- needs next candle confirmation

**Doji Star** | Reliability: Moderate
- Doji after strong trend signals hesitation
- Best when combined with overbought/oversold indicators

**Abandoned Baby** | Reliability: High (when genuine)
- Rare gap pattern with doji gapping away from trend
- Very strong when it appears, but appears infrequently

**Hanging Man** | Reliability: Moderate
- Same shape as Hammer but appears at top of uptrend (bearish)
- Needs confirmation -- next candle must close below Hanging Man body
""")

    # ── Continuation ──
    with st.expander("Continuation Patterns (Trend Persists)", expanded=False):
        st.markdown("""
These patterns suggest the current trend will continue after a brief pause.

**Rising Three Methods** | Reliability: Moderate-High
- Uptrend: Large green, 3 small red candles (pullback within range), large green
- Signals trend continuation after a healthy pause

**Falling Three Methods** | Reliability: Moderate-High
- Downtrend version: Large red, 3 small green (retracement), large red
- Confirms downtrend is intact

**Separating Lines** | Reliability: Moderate
- Two candles open at same level, close in trend direction
- Confirms continuation of current move

**Mat Hold** | Reliability: Moderate-High
- Bullish continuation -- rare but reliable
- Large green, small counter-trend candles, final green resumes trend

**Tasuki Gap** | Reliability: Moderate
- Gap continuation pattern confirming trend
- Gap acts as support (bullish) or resistance (bearish)
""")

    # ── Indecision ──
    with st.expander("Indecision Patterns (Wait for Confirmation)", expanded=False):
        st.markdown("""
These patterns signal uncertainty. **DO NOT trade these alone** -- wait for the
next candle to confirm direction.

**Doji** -- Open equals Close (cross shape). Equilibrium between buyers and sellers.

**Spinning Top** -- Small body, equal upper/lower shadows. Indecision in market.

**High-Wave Candle** -- Very long upper and lower shadows, small body. Extreme indecision.

**Long Legged Doji** -- Doji with very long shadows. Intense battle between bulls and bears.

---

### Pattern Trading Tips

1. **Always wait for confirmation** -- Most patterns need the next candle to confirm
2. **Volume matters** -- Patterns with high volume are far more reliable
3. **Context is king** -- Hammer at support after downtrend >> random hammer in uptrend
4. **Combine with indicators** -- Pattern + RSI oversold + support = high probability
5. **Don't chase** -- If you miss the entry, wait for the next setup
""")


# ── Section 4 ──────────────────────────────────────────────────────────────
def _render_trading_combinations():
    st.subheader("Best Trading Combinations")
    st.markdown(
        "These are **proven setups** combining indicators and patterns. Each "
        "has specific entry rules, risk levels, and expected outcomes."
    )

    # ── Combo 1: Trend Following ──
    st.success("""
### Combo 1: Trend Following Setup

**Setup Requirements:**
- EMA Alignment: Price > EMA20 > EMA50 > EMA200 (strong uptrend)
- ADX > 25 (confirms trend strength)
- Volume spike > 1.5x average on key candles
- Bullish pattern near EMA20 (Hammer, Bullish Engulfing, or Morning Star)

**Entry Signal:**
1. Wait for pullback to EMA20 in strong uptrend
2. Bullish reversal pattern forms at EMA20
3. Volume confirms (> 1.5x average)
4. ADX rising or > 25
5. Enter on next candle open or break of pattern high

**Stop Loss:** Below pattern low OR 1.5x ATR below entry

**Target:**
- First target: 2:1 risk-reward
- Trail stop to EMA20 after first target hit

**Best For:** Swing trading in trending markets (holding 5-20 days)

**Risk Level:** Medium | **Expected Win Rate:** ~60-65%

**Example:**
Stock in strong uptrend (EMA aligned), pulls back to EMA20, forms Hammer with 2.1x volume, ADX = 32 and rising. Enter on next candle, stop below Hammer low.

**Common Failure:** EMA20 breaks -- this means the trend may be reversing. Always honour stop-loss.
""")

    # ── Combo 2: Mean Reversion ──
    st.info("""
### Combo 2: Mean Reversion / Oversold Bounce

**Setup Requirements:**
- RSI < 30 (oversold)
- Price at or below lower Bollinger Band
- Reversal candlestick (Hammer, Morning Star, Bullish Engulfing)
- Nearby support level (previous low, S/R zone)

**Entry Signal:**
1. RSI drops below 30
2. Price touches or pierces lower Bollinger Band
3. Bullish reversal pattern appears
4. Check for support zone nearby (increases probability)
5. Enter on pattern confirmation

**Stop Loss:** Below pattern low or 2% below entry (whichever is tighter)

**Target:**
- First: Middle Bollinger Band (20 SMA)
- Second: Upper Bollinger Band or RSI = 70

**Best For:** Counter-trend plays in ranging markets (1-5 day holds)

**Risk Level:** High (counter-trend) | **Expected Win Rate:** ~55-60%

**Warning:** This is counter-trend! NEVER use in strong downtrends (EMA bearish alignment).
Works best in ranging markets where ADX < 20. Must cut losses quickly (2% max).
""")

    # ── Combo 3: Breakout ──
    st.success("""
### Combo 3: Breakout Confirmation

**Setup Requirements:**
- Price breaking out above consolidation range (15+ days tight range)
- Volume spike > 1.5x (ideally > 2x average)
- MACD bullish crossover (MACD crosses above signal line)
- ADX rising from < 20 (new trend forming)

**Entry Signal:**
1. Identify consolidation (tight range, ADX < 20)
2. Breakout candle closes above resistance with high volume
3. MACD crosses above signal line
4. ADX starts rising
5. Enter on breakout candle close or next open

**Stop Loss:** Below consolidation range OR below breakout candle low

**Target:** Measured move -- add consolidation height to breakout point
(e.g., range 245-255, break at 255, target = 265)

**Best For:** Momentum trading (3-10 day holds)

**Risk Level:** Medium | **Expected Win Rate:** ~58-62%

**False Breakout Warning:**
- Low volume breakout? IGNORE IT.
- ADX stays flat? Probably not a real trend.
- Use ATR-based stops to survive shakeouts.
- Some traders wait for retest of breakout level before entering (lower risk).
""")

    # ── Combo 4: Sell / Short ──
    st.warning("""
### Combo 4: Sell / Short Setup

**Setup Requirements:**
- RSI > 70 (overbought)
- Bearish reversal pattern (Evening Star, Shooting Star, Bearish Engulfing, Dark Cloud Cover)
- Price at or above upper Bollinger Band
- EMA bearish alignment (20 < 50 < 200) OR losing EMA20 support

**Entry Signal:**
1. RSI climbs above 70
2. Bearish reversal pattern forms at resistance
3. Price at upper Bollinger Band
4. Volume confirms reversal
5. Enter on pattern confirmation

**Stop Loss:** Above pattern high or 2% above entry

**Target:**
- First: Middle Bollinger Band
- Second: Lower Bollinger Band or RSI = 30

**Best For:**
- Short entries (via F&O or intraday MIS)
- Profit-taking signals on existing long positions
- Avoiding new longs

**Risk Level:** Medium | **Expected Win Rate:** ~55-60%

**Indian Market Note:** Shorting is intraday only (MIS) or via F&O. Most traders use this
setup to (a) exit longs, (b) avoid new longs, or (c) buy put options on F&O stocks.
""")

    # ── Combo 5: Index Options Short Straddle ──
    st.info("""
### Combo 5: Index Options - Short Straddle Setup

*Tailored for Nifty / BankNifty weekly options trading*

**Setup Requirements:**
- VIX < 15 (low volatility environment)
- PCR (Put-Call Ratio) between 0.8-1.2 (neutral sentiment)
- Spot price within 1% of Max Pain level
- ADX < 20 (no trending market, ranging expected)
- Entry on Thursday for weekly expiry (1-day theta decay)

**Entry Signal:**
1. Check VIX -- must be < 15
2. Check PCR in F&O Data tab -- aim for 0.9-1.1
3. Check Max Pain -- spot within 1%
4. Check ADX -- should be < 20
5. Enter Thursday 10:00-10:30 AM
6. Sell ATM Call + ATM Put

**Strike Selection:**
- Nifty: Round to nearest 50 (e.g., spot 24,235 --> ATM 24,250)
- BankNifty: Round to nearest 100 (e.g., spot 51,870 --> ATM 51,900)
- Aim for combined premium: 150-250 pts (Nifty), 300-500 pts (BankNifty)

**Stop Loss / Management:**
- Exit if spot moves > 2% from entry level
- Exit if VIX spikes above 20
- Book profits at 60-70% of max profit
- Friday morning: if profitable and spot near Max Pain, hold till 3 PM

**Risk Level:** Low (in proper setup) / High (if misused in trending market)

**Expected Win Rate:** ~65-70% in ranging markets, < 40% in trending markets

**NEVER short straddle during:**
- Event days (RBI policy, Budget, Fed meeting, major results)
- High VIX (> 20)
- Strong trending markets (ADX > 25)

**Lower Risk Alternative:** Use Iron Condor instead (sell ATM straddle, buy OTM wings).
Example: Sell 24,300 CE/PE, Buy 24,500 CE + 24,100 PE = defined risk.
""")

    st.markdown("""
### Combination Strategy Tips

1. **Don't force trades** -- Wait for proper setups (patience is key)
2. **Risk management > Win rate** -- 50% win rate with 2:1 reward-risk is profitable
3. **Position sizing** -- Never risk > 2% of capital per trade
4. **Keep a trading journal** -- Track which setups work best for YOUR style
5. **Market context matters** -- Trend setups fail in ranging markets, mean reversion fails in trends
6. **Combine with S/R levels** -- All setups are more reliable at key support / resistance
""")


# ── Section 5 ──────────────────────────────────────────────────────────────
def _render_scoring_system():
    st.subheader("Alert Scoring System Explained")
    st.markdown(
        "The **Alerts/Summary** tab scores every stock by combining multiple "
        "technical signals. Here is exactly how it works."
    )

    st.markdown("""
### How Scoring Works

Each stock gets **two scores** calculated separately:
- **Bullish Score** (counts bullish signals)
- **Bearish Score** (counts bearish signals)

The **higher score** determines the alert direction. Only stocks with score >= 3
(default threshold) appear in alerts.

### Point System

| Criteria | Bullish Signal | Pts | Bearish Signal | Pts |
|----------|----------------|-----|----------------|-----|
| **RSI** | < 30 (oversold) | +1 | > 70 (overbought) | +1 |
| **MACD** | Bullish crossover / above signal | +1 | Bearish crossover / below signal | +1 |
| **EMA Trend** | Price > EMA20 > EMA50 > EMA200 | +1 | Price < EMA20 < EMA50 < EMA200 | +1 |
| **Bollinger Band** | Price near lower band | +1 | Price near upper band | +1 |
| **ADX** | Strong bullish (ADX > 25, +DI > -DI) | +1 | Strong bearish (ADX > 25, -DI > +DI) | +1 |
| **Volume** | High volume confirming direction | +1 | High volume confirming direction | +1 |
| **Breakout** | Breaking out of consolidation | **+2** | Breaking down | **+2** |
| **Candlestick** | Bullish pattern(s) detected | +1 to +2 | Bearish pattern(s) detected | +1 to +2 |

*Breakout/Breakdown gets +2 (double weight). Candlestick gets +2 if multiple patterns detected.*

### Score Levels & Interpretation

| Score | Strength | Interpretation | Action |
|-------|----------|----------------|--------|
| 1-2 | Weak | Only 1-2 confirming signals | Avoid or wait for more confirmation |
| 3-4 | Moderate | Some confluence present | Good watchlist candidates, verify manually |
| 5-6 | Strong | Multiple confirmations aligned | High-probability setups |
| 7+ | Very Strong | Rare, high confluence | Priority trades (still verify chart!) |

### Example Calculation

**Stock: RELIANCE**

| Signal | Value | Score |
|--------|-------|-------|
| RSI | 28 (oversold) | +1 bullish |
| MACD | Bullish crossover | +1 bullish |
| EMA | Price > EMA20 > EMA50 > EMA200 | +1 bullish |
| Bollinger | Price at lower band | +1 bullish |
| ADX | 28, +DI > -DI | +1 bullish |
| Volume | 2.1x average | +1 bullish |
| Candlestick | Hammer detected | +1 bullish |

**Total Bullish Score: 7** (Very Strong) | Bearish Score: 0

### Using Scores Effectively

1. **Start with score >= 5** when learning (higher quality setups)
2. **Score 3-4** can work if you manually verify the chart and see a clean setup
3. **Don't blindly follow score 10** -- always check the Chart tab visually
4. **Compare bullish vs bearish** -- If bullish = 5 and bearish = 4, it is mixed (be cautious)
5. **Use with other tabs** -- High score in Alerts -> Check Chart -> Verify Technicals -> Decide

### Limitations

- **Lagging indicators** -- All technical indicators lag price, they are not predictive
- **No fundamental analysis** -- Scoring ignores news, earnings, sector trends
- **Market context** -- A score-7 bullish signal in a bear market is riskier than in a bull market
""")


# ── Section 6 ──────────────────────────────────────────────────────────────
def _render_quick_reference():
    st.subheader("Quick Reference Card")

    st.markdown("""
### Indicator Signals at a Glance

| Indicator | Bullish Signal | Bearish Signal | Best Timeframe |
|-----------|----------------|----------------|----------------|
| **EMA** | Price > EMA20 > EMA50 > EMA200 | Price < EMA20 < EMA50 < EMA200 | Daily / Weekly |
| **RSI** | < 30 (oversold bounce) | > 70 (overbought reversal) | Daily |
| **MACD** | MACD crosses above signal line | MACD crosses below signal line | Daily / Weekly |
| **Bollinger** | Price at / below lower band | Price at / above upper band | Daily |
| **ADX** | > 25 with +DI > -DI | > 25 with -DI > +DI | Daily / Weekly |
| **Volume** | > 1.5x avg on bullish move | > 1.5x avg on bearish move | Intraday / Daily |
| **ATR** | Rising = volatility up (size down) | Use 1.5x ATR for stop-loss | All |
| **VWAP** | Price > VWAP (buyers control) | Price < VWAP (sellers control) | Intraday only |

### Pattern Quick Guide

**Strong Reversal (High Reliability):**
- Bullish: Hammer, Morning Star, Bullish Engulfing, Piercing, Three White Soldiers
- Bearish: Shooting Star, Evening Star, Bearish Engulfing, Dark Cloud, Three Black Crows

**Moderate Reversal (Needs Confirmation):**
- Inverted Hammer, Harami, Doji Star, Abandoned Baby, Hanging Man

**Continuation (Trend Persists):**
- Rising / Falling Three Methods, Separating Lines, Mat Hold, Tasuki Gap

**Indecision (Wait & Watch):**
- Doji, Spinning Top, High-Wave, Long Legged Doji

### Top 5 Trading Rules

1. **Combine 2-3 indicators minimum** -- No single indicator is 100% reliable
2. **Volume confirms conviction** -- Low volume moves are weak and likely to reverse
3. **Trend is your friend** -- Don't fight strong trends (ADX > 25)
4. **S/R levels matter** -- Signals at support / resistance are 2x more reliable
5. **Always use a stop-loss** -- Technical analysis is probability, not certainty

### Risk Management Checklist

- Position size <= 2% of capital per trade
- Stop-loss set BEFORE entry (1.5x ATR or below pattern)
- Risk-reward ratio >= 1.5 : 1 (preferably 2 : 1)
- Check market mood (trending vs ranging)
- Verify chart visually (don't trade on numbers alone)
- Check for upcoming events (earnings, RBI policy, budget, FOMC)
""")

    st.markdown("---")
    st.caption(
        "This is educational content for learning technical analysis. "
        "All trading involves risk. Past performance does not guarantee future results. "
        "Always do your own research and never risk more than you can afford to lose. "
        "Position sizing is more important than win rate."
    )
