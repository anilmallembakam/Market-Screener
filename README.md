# Daily Trading Screener

A powerful Streamlit-based stock screening and alert tracking application for US and Indian markets.

## Features

### Stock Screening & Alerts
- **Multi-criteria scoring system** - Scores stocks 1-10 based on technical indicators
- **Pattern detection** - Identifies candlestick patterns (Hammer, Engulfing, Doji, etc.)
- **Trading setups** - Recommends option strategies (Bull Call Spread, Iron Condor, etc.)
- **Direction signals** - Bullish/Bearish classification with confidence scoring
- **Option Flow Links** - Direct links to Unusual Whales for options analysis

### Performance Tracker
- **Historical alert tracking** - Save and monitor alerts over 5-20 days
- **P&L calculation** - Track gains, losses, max drawdown
- **Momentum detection** - Identifies stocks "Losing Steam" for timely exits
- **Calendar view** - Go back to any date and see performance till today
- **Weekly summary** - End-of-week reports with win rates by direction/market

### Winner Analytics
- **Score analysis** - Which scores produce best winners
- **Pattern analysis** - Most successful candlestick patterns
- **Setup analysis** - Best performing trading strategies
- **Criteria breakdown** - Key technical factors in winning trades
- **Winners vs Losers comparison** - Side-by-side profile comparison

### Auto-Save System
- **Market-aware scheduling** - Tracks US (4:00 PM ET) and Indian (3:30 PM IST) close times
- **Score filtering** - Only saves alerts with Score >= 5
- **Duplicate prevention** - Won't save same alert twice per day

### Smart Data Caching
- **Local file caching** - Stores data in `.data_cache/` folder
- **Instant page loads** - No Yahoo Finance calls on refresh
- **Manual refresh button** - Fetch fresh data when needed
- **Cache status display** - Shows last update time and stock count

## Tabs

| Tab | Description |
|-----|-------------|
| **Alerts/Summary** | Main screening results with scores, patterns, setups |
| **Pattern Scanner** | Candlestick pattern detection |
| **Technicals** | Technical indicator analysis |
| **Breakouts** | Breakout/breakdown detection |
| **S/R Levels** | Support/Resistance levels |
| **F&O Data** | Futures & Options data |
| **Trade Signals** | Buy/Sell signal generation |
| **Chart** | Interactive price charts |
| **Backtest** | Strategy backtesting |
| **Tracker** | Performance tracking & analytics |
| **Guide** | Usage documentation |

## Project Structure

```
DailyScreener/
├── screener/
│   ├── app.py                 # Main Streamlit app
│   ├── config.py              # Configuration constants
│   ├── data_fetcher.py        # Yahoo Finance data fetching with caching
│   ├── stock_lists.py         # Stock universe definitions
│   ├── alerts.py              # Alert generation & scoring
│   ├── alert_history.py       # Alert storage & performance tracking
│   ├── scheduler.py           # Auto-save scheduling
│   ├── indicators.py          # Technical indicators
│   ├── patterns.py            # Candlestick pattern detection
│   ├── backfill_alerts.py     # Historical alert backfilling
│   └── pages/
│       ├── page_alerts.py     # Alerts tab
│       ├── page_tracker.py    # Performance tracker tab
│       ├── page_scanner.py    # Pattern scanner tab
│       └── ...                # Other page modules
├── .data_cache/               # Cached market data (auto-generated)
├── .alert_history/            # Alert history storage (auto-generated)
├── requirements.txt
└── README.md
```

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd DailyScreener

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run the app
streamlit run screener/app.py
```

The app will open in your browser at `http://localhost:8501`

## Configuration

Key settings in `screener/config.py`:
- `DEFAULT_LOOKBACK_DAYS` - Days of historical data (default: 365)
- `CACHE_TTL_SECONDS` - Streamlit cache TTL (default: 900)
- Technical indicator periods (EMA, RSI, MACD, etc.)

## Markets Supported

| Market | Indices |
|--------|---------|
| **US** | S&P 500 |
| **Indian** | Nifty 50, Nifty 200, BankNifty |

## Data Storage

- **No database required** - Uses JSON files for alert history
- **Pickle files** - For cached market data
- **Fully local** - All data stored in project directory

### Auto-generated folders:
- `.data_cache/` - Cached OHLCV data (pickle files)
- `.alert_history/` - Alert history and scheduler state (JSON files)

## Backfilling Historical Alerts

To backfill historical alerts for analysis:

```bash
python -m screener.backfill_alerts
```

This will generate alerts for past trading days and save them to history.

## Key Dependencies

- `streamlit` - Web UI framework
- `yfinance` - Yahoo Finance data
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `pytz` - Timezone handling

## License

MIT License
