"""
Backfill historical alerts for Indian market only.
"""
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
import json
import time

from screener.stock_lists import get_stock_list
from screener.alerts import generate_alerts
from screener.config import DEFAULT_LOOKBACK_DAYS


# Storage path
_HISTORY_DIR = Path(__file__).resolve().parent.parent / '.alert_history'
_HISTORY_FILE = _HISTORY_DIR / 'alerts.json'


def load_history():
    if not _HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(_HISTORY_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(history):
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE.write_text(
        json.dumps(history, default=str, indent=2),
        encoding='utf-8'
    )


def fetch_historical_data(symbols: list, end_date: str, lookback_days: int = 100) -> dict:
    """Fetch historical data ending at a specific date."""
    end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    start = end - timedelta(days=lookback_days + 50)

    data = {}

    try:
        tickers_str = " ".join(symbols)
        df = yf.download(
            tickers_str,
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
            group_by='ticker',
            progress=False,
            threads=True
        )

        for symbol in symbols:
            try:
                if len(symbols) == 1:
                    symbol_df = df.copy()
                else:
                    symbol_df = df[symbol].copy()

                symbol_df = symbol_df[symbol_df.index <= end_date]

                if not symbol_df.empty and len(symbol_df) >= 20:
                    symbol_df = symbol_df.tail(lookback_days)
                    data[symbol] = symbol_df
            except Exception:
                continue

    except Exception as e:
        print(f"Error fetching batch data: {e}")

    return data


def main():
    start_date = "2026-01-01"
    end_date = datetime.now().strftime('%Y-%m-%d')
    min_score = 5
    market = 'indian'

    print(f"\nBackfilling INDIAN market from {start_date} to {end_date}")

    symbols, _ = get_stock_list('indian', 'nifty200')
    print(f"Loaded {len(symbols)} symbols")

    # Get trading days using RELIANCE.NS
    try:
        ref = yf.Ticker("RELIANCE.NS")
        hist = ref.history(start=start_date, end=end_date)
        trading_days = [d.strftime('%Y-%m-%d') for d in hist.index]
    except Exception as e:
        print(f"Error getting trading days: {e}")
        return

    print(f"Found {len(trading_days)} trading days")

    history = load_history()
    existing_keys = {(a['symbol'], a['date'], a.get('market', 'us')) for a in history}

    total_new_alerts = 0

    for i, trade_date in enumerate(trading_days):
        print(f"\n[{i+1}/{len(trading_days)}] Processing {trade_date}...")

        daily_data = fetch_historical_data(symbols, trade_date, DEFAULT_LOOKBACK_DAYS)

        if not daily_data:
            print(f"  No data available")
            continue

        print(f"  Loaded data for {len(daily_data)} stocks")

        try:
            alerts_df = generate_alerts(daily_data, min_score=min_score)
        except Exception as e:
            print(f"  Error generating alerts: {e}")
            continue

        if alerts_df.empty:
            print(f"  No alerts with score >= {min_score}")
            continue

        new_count = 0
        for _, row in alerts_df.iterrows():
            symbol = row['Symbol']
            key = (symbol, trade_date, market)

            if key in existing_keys:
                continue

            alert_price = 0.0
            if symbol in daily_data and not daily_data[symbol].empty:
                alert_price = float(daily_data[symbol]['Close'].iloc[-1])

            alert_record = {
                'symbol': symbol,
                'date': trade_date,
                'direction': row['Direction'],
                'score': int(row['Score']),
                'alert_price': alert_price,
                'criteria': row.get('Top Criteria', ''),
                'pattern': row.get('Pattern', ''),
                'combo': row.get('Combo', ''),
                'market': market,
            }
            history.append(alert_record)
            existing_keys.add(key)
            new_count += 1

        if new_count > 0:
            print(f"  + Added {new_count} alerts")
            total_new_alerts += new_count

            if i % 3 == 0:
                save_history(history)
                print(f"  [Saved {len(history)} total alerts]")

        time.sleep(1)  # Longer delay to avoid rate limiting

    save_history(history)
    print(f"\nCOMPLETED INDIAN: Added {total_new_alerts} new alerts")
    print(f"Total alerts in history: {len(history)}")


if __name__ == "__main__":
    main()
