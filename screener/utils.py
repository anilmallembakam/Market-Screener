"""Shared utility functions for the screener app."""


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
