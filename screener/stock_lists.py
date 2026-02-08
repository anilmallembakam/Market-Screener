from typing import List, Tuple


def get_nifty50() -> List[str]:
    symbols = [
        "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
        "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BPCL", "BHARTIARTL",
        "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY",
        "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
        "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC",
        "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT",
        "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC",
        "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SUNPHARMA",
        "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM",
        "TITAN", "ULTRACEMCO", "UPL", "WIPRO", "LTIM",
    ]
    return [f"{s}.NS" for s in symbols]


def get_nifty200() -> List[str]:
    symbols = [
        "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "AMBUJACEM",
        "APOLLOHOSP", "ASIANPAINT", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO",
        "BAJFINANCE", "BAJAJFINSV", "BALKRISIND", "BANDHANBNK", "BANKBARODA",
        "BEL", "BERGEPAINT", "BHARATFORG", "BHARTIARTL", "BIOCON",
        "BOSCHLTD", "BPCL", "BRITANNIA", "CANBK", "CHOLAFIN",
        "CIPLA", "COALINDIA", "COFORGE", "COLPAL", "CONCOR",
        "CROMPTON", "CUB", "CUMMINSIND", "DABUR", "DALBHARAT",
        "DEEPAKNTR", "DIVISLAB", "DIXON", "DLF", "DRREDDY",
        "EICHERMOT", "ESCORTS", "EXIDEIND", "FEDERALBNK", "GAIL",
        "GLENMARK", "GMRINFRA", "GNFC", "GODREJCP", "GODREJPROP",
        "GRASIM", "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH",
        "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
        "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "HONAUT", "ICICIBANK",
        "ICICIGI", "ICICIPRULI", "IDEA", "IDFCFIRSTB", "IEX",
        "IGL", "INDHOTEL", "INDIAMART", "INDIGO", "INDUSINDBK",
        "INDUSTOWER", "INFY", "IOC", "IPCALAB", "IRCTC",
        "ITC", "JINDALSTEL", "JSWENERGY", "JSWSTEEL", "JUBLFOOD",
        "KOTAKBANK", "LALPATHLAB", "LAURUSLABS", "LICHSGFIN", "LT",
        "LTIM", "LTTS", "LUPIN", "M&M", "M&MFIN",
        "MANAPPURAM", "MARICO", "MARUTI", "MCDOWELL-N", "MCX",
        "METROPOLIS", "MFSL", "MGL", "MOTHERSON", "MPHASIS",
        "MRF", "MUTHOOTFIN", "NATIONALUM", "NAUKRI", "NAVINFLUOR",
        "NESTLEIND", "NMDC", "NTPC", "OBEROIRLTY", "OFSS",
        "ONGC", "PAGEIND", "PEL", "PERSISTENT", "PETRONET",
        "PFC", "PIDILITIND", "PIIND", "PNB", "POLYCAB",
        "POWERGRID", "PVRINOX", "RAMCOCEM", "RBLBANK", "RECLTD",
        "RELIANCE", "SAIL", "SBICARD", "SBILIFE", "SBIN",
        "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SRF", "SUNPHARMA",
        "SUNTV", "SYNGENE", "TATACHEM", "TATACOMM", "TATACONSUM",
        "TATAELXSI", "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TCS",
        "TECHM", "TITAN", "TORNTPHARM", "TORNTPOWER", "TRENT",
        "TVSMOTOR", "UBL", "ULTRACEMCO", "UNIONBANK", "UPL",
        "VEDL", "VOLTAS", "WIPRO", "ZEEL", "ZYDUSLIFE",
    ]
    return [f"{s}.NS" for s in symbols]


def get_banknifty() -> List[str]:
    symbols = [
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
        "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "PNB", "IDFCFIRSTB",
        "BANKBARODA", "AUBANK",
    ]
    return [f"{s}.NS" for s in symbols]


def get_sp500() -> List[str]:
    """Current S&P 500 components as of February 2026."""
    symbols = [
        # Top holdings and mega caps
        "NVDA", "AAPL", "GOOG", "GOOGL", "MSFT", "AMZN", "META", "AVGO", "TSLA", "BRK.B",
        "WMT", "LLY", "JPM", "V", "XOM", "JNJ", "MA", "COST", "MU", "ORCL",
        # Financials & Banks
        "BAC", "GS", "WFC", "MS", "C", "SCHW", "BLK", "BX", "COF", "AXP",
        "PNC", "USB", "TFC", "BK", "STT", "MTB", "FITB", "CFG", "HBAN", "KEY",
        "RF", "NTRS", "SYF", "IBKR", "RJF", "PFG", "AIG", "PRU", "MET", "AFL",
        "ALL", "TRV", "CB", "PGR", "HIG", "ACGL", "BRO", "AJG", "AON", "MMC",
        # Technology
        "ABBV", "HD", "PG", "CVX", "NFLX", "KO", "CAT", "AMD", "GE", "CSCO",
        "PLTR", "MRK", "LRCX", "PM", "IBM", "RTX", "AMAT", "INTC", "PEP", "MCD",
        "TMUS", "GEV", "LIN", "AMGN", "TMO", "TXN", "VZ", "ABT", "DIS", "T",
        "BA", "GILD", "KLAC", "NEE", "CRM", "ISRG", "ANET", "TJX", "APH", "DE",
        "ADI", "LOW", "UBER", "PFE", "DHR", "HON", "UNP", "ACN", "QCOM", "ETN",
        "BKNG", "LMT", "APP", "SYK", "WELL", "SPGI", "MDT", "COP", "PLD", "BMY",
        "NEM", "INTU", "PH", "VRTX", "MCK", "HCA", "SBUX", "BSX", "CMCSA", "PANW",
        "ADBE", "MO", "CME", "NOW", "GLW", "TT", "NOC", "CRWD", "UPS", "CVS",
        "SO", "GD", "ICE", "WDC", "DUK", "CEG", "NKE", "RCL", "STX", "ADP",
        "KKR", "WM", "MMM", "HWM", "MAR", "SHW", "EMR", "CVNA", "FCX",
        "FDX", "CRH", "ITW", "JCI", "EQIX", "ECL", "WMB", "SNPS", "MCO", "MNST",
        "REGN", "DELL", "AMT", "CMI", "ORLY", "DASH", "CTAS", "CI", "APO", "CDNS",
        "MDLZ", "GM", "CL", "SPG", "SLB", "PWR", "CSX", "ELV", "HOOD", "ABNB",
        "HLT", "TDG", "MSI", "COR", "NSC", "RSG", "KMI", "WBD", "PCAR", "LHX",
        "AEP", "PSX", "TEL", "APD", "VLO", "ROST", "EOG", "FTNT", "AZO", "DLR",
        "MPWR", "MPC", "BDX", "O", "BKR", "SRE", "GWW", "URI", "NXPI", "ZTS",
        "F", "FAST", "CARR", "AME", "CAH", "D", "TGT", "OKE", "IDXX", "CMG",
        "ADSK", "VST", "PSA", "EA", "CBRE", "AMP", "DAL", "CTVA", "NDAQ", "FANG",
        "TER", "CCL", "HSY", "ROK", "EW", "OXY", "TRGP", "DHI", "YUM", "XEL",
        "EXC", "COIN", "ETR", "NUE", "FIX", "WDAY", "VMC", "KR", "ARES", "ODFL",
        "WAB", "MLM", "SYY", "TKO", "MCHP", "MSCI", "PEG", "KEYS", "RMD", "VTR",
        "DDOG", "EBAY", "CPRT", "IR", "GRMN", "LVS", "ED", "ROP", "KDP", "UAL",
        "PYPL", "CTSH", "GEHC", "A", "WEC", "TTWO", "PCG", "EL", "EQT", "PAYX",
        "CCI", "OTIS", "KVUE", "KMB", "XYL", "EME", "FICO", "NRG", "AXON", "CHTR",
        "LYV", "DG", "FISV", "ADM", "IQV", "HPE", "WTW", "ROL", "EXR", "TPR",
        "VICI", "DOV", "ULTA", "TDY", "STLD", "BIIB", "TSCO", "HAL", "KHC", "EXPE",
        "CBOE", "STZ", "AEE", "PPG", "ATO", "IRM", "LEN", "DTE", "MTD", "FOXA",
        "DXCM", "JBL", "DVN", "CINF", "FE", "FIS", "HUBB", "LUV", "PPL", "WRB",
        "WSM", "ON", "CNP", "FOX", "PHM", "GIS", "ES", "TPL", "VRSK",
        "DRI", "CPAY", "EQR", "STE", "LDOS", "EIX", "DLTR", "IP", "AVB", "AWK",
        "CHD", "CHRW", "EFX", "FSLR", "HUM", "CTRA", "L", "SW", "LH", "TSN",
        "DOW", "WAT", "VLTO", "NVR", "BG", "AMCR", "CMS", "EXPD", "OMC", "JBHT",
        "PKG", "CSGP", "INCY", "BR", "DGX", "NI", "RL", "TROW", "GPC", "SMCI",
        "VRSN", "NTAP", "GPN", "LULU", "DD", "SBAC", "ALB", "SNA", "WY", "IFF",
        "CNC", "FTV", "LII", "CDW", "PTC", "MKC", "HPQ", "WST", "ZBH", "BALL",
        "LYB", "EVRG", "APTV", "J", "ESS", "LNT", "PODD", "TXT", "VTRS", "HOLX",
        "DECK", "INVH", "NDSN", "COO", "MRNA", "PNR", "MAA", "IEX", "TRMB", "FFIV",
        "HII", "ALLE", "MAS", "ERIE", "TYL", "KIM", "AVY", "BBY", "GEN", "CF",
        "CLX", "BEN", "REG", "SWK", "BLDR", "HRL", "AKAM", "UHS", "BF.B", "UDR",
        "SOLV", "HST", "ALGN", "EG", "DPZ", "HAS", "GDDY", "TTD", "NWS", "ZBRA",
        "JKHY", "NWSA", "AIZ", "WYNN", "DOC", "IVZ", "SJM", "GL", "RVTY", "CPT",
        "BXP", "AES", "IT", "PNW", "BAX", "AOS", "GNRC", "NCLH", "TECH", "EPAM",
        "TAP", "POOL", "APA", "ARE", "MGM", "DVA", "HSIC", "SWKS", "CRL", "CAG",
        "FRT", "MOS", "CPB", "FDS", "MTCH", "PAYC", "LW", "MOH", "UNH",
    ]
    return symbols


def get_stock_list(market: str, index: str) -> Tuple[List[str], str]:
    mapping = {
        ('indian', 'nifty50'): (get_nifty50, '^NSEI'),
        ('indian', 'nifty200'): (get_nifty200, '^NSEI'),
        ('indian', 'banknifty'): (get_banknifty, '^NSEBANK'),
        ('us', 'sp500'): (get_sp500, '^GSPC'),
    }
    key = (market.lower(), index.lower().replace(' ', '').replace('&', ''))
    if key in mapping:
        func, idx_sym = mapping[key]
        return func(), idx_sym
    return [], ''
