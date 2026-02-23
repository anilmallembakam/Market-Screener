"""Shared utility functions for the screener app."""
from urllib.parse import quote


def get_unusual_whales_url(symbol: str) -> str:
    """Generate Unusual Whales option flow URL for a symbol."""
    ticker = symbol.replace('.NS', '')
    base_url = "https://unusualwhales.com/live-options-flow"
    params = (
        f"?limit=50"
        f"&ticker_symbol={quote(ticker)}"
        f"&excluded_tags[]=no_side"
        f"&excluded_tags[]=mid_side"
        f"&excluded_tags[]=bid_side"
        f"&excluded_tags[]=china"
        f"&min_open_interest=1"
        f"&report_flag[]=sweep"
        f"&report_flag[]=floor"
        f"&report_flag[]=normal"
        f"&add_agg_trades=true"
        f"&is_multi_leg=false"
        f"&min_ask_perc=0.6"
        f"&min_premium=10000"
    )
    return base_url + params


def get_chart_url(symbol: str) -> str:
    """Generate TradingView chart URL for a symbol."""
    # Remove .NS suffix for URL, TradingView uses NSE: prefix for Indian stocks
    if symbol.endswith('.NS'):
        clean_symbol = symbol.replace('.NS', '')
        return f"https://www.tradingview.com/chart/?symbol=NSE%3A{clean_symbol}"
    else:
        return f"https://www.tradingview.com/chart/?symbol={symbol}"


def get_clean_symbol(symbol: str) -> str:
    """Get clean symbol name without exchange suffix."""
    return symbol.replace('.NS', '') if symbol.endswith('.NS') else symbol
