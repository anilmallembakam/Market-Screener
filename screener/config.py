import pytz
from pathlib import Path

# Paths
SCREENER_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCREENER_DIR.parent

# Timezone
TZ_INDIA = pytz.timezone('Asia/Kolkata')
TZ_US = pytz.timezone('US/Eastern')

# Data defaults
DEFAULT_LOOKBACK_DAYS = 365
WEEKLY_LOOKBACK_DAYS = 730
CACHE_TTL_SECONDS = 900  # 15-minute Streamlit cache

# Technical indicator defaults
EMA_PERIODS = [20, 50, 200]
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2
ADX_PERIOD = 14

# Consolidation/breakout defaults
CONSOLIDATION_LOOKBACK = 15
CONSOLIDATION_PERCENTAGE = 2.0
BREAKOUT_PERCENTAGE = 2.5
BREAKOUT_VOLUME_FACTOR = 1.5  # Breakout must have volume >= 1.5x 20-day avg

# Entry signal thresholds (Trend Following)
ENTRY_EMA_PULLBACK_PCT = 2.0       # max % distance from EMA20 for pullback
ENTRY_ADX_MIN = 25                  # minimum ADX for trend strength
ENTRY_VOLUME_RATIO_PREFERRED = 1.5  # volume ratio for "confirmed" signal

# S/R detection
SR_PIVOT_WINDOW = 5
SR_CLUSTER_TOLERANCE_PCT = 1.5

# Market Mood thresholds
VIX_HIGH_INDIA = 20
VIX_LOW_INDIA = 13
VIX_HIGH_US = 25
VIX_LOW_US = 15
MOOD_WEIGHT_BULL_PCT = 0.4
MOOD_WEIGHT_EMA_BREADTH = 0.3
MOOD_WEIGHT_RSI = 0.3

# Strike rounding for index options
NIFTY_STRIKE_STEP = 50
BANKNIFTY_STRIKE_STEP = 100
