"""
Backfill historical alerts from January 2026 to now.
This script simulates running the screener for each trading day and saves alerts.
Supports both Google Sheets (for cloud) and local JSON storage.
"""
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
import json
import time
import os

from screener.stock_lists import get_stock_list
from screener.alerts import generate_alerts
from screener.config import DEFAULT_LOOKBACK_DAYS


# Storage path (local fallback)
_HISTORY_DIR = Path(__file__).resolve().parent.parent / '.alert_history'
_HISTORY_FILE = _HISTORY_DIR / 'alerts.json'

# Google Sheets client (initialized if available)
_gsheet_client = None
_gsheet_worksheet = None


def init_gsheet():
    """Initialize Google Sheets connection for backfill."""
    global _gsheet_client, _gsheet_worksheet

    try:
        from google.oauth2.service_account import Credentials
        import gspread

        # Try to load credentials from environment or local file
        creds_file = Path(__file__).resolve().parent.parent / '.streamlit' / 'secrets.toml'

        if creds_file.exists():
            import toml
            secrets = toml.load(creds_file)
            creds_dict = secrets.get('gcp_service_account', {})
            spreadsheet_id = secrets.get('spreadsheet_id', '')
        else:
            # Try environment variables (for CI/CD)
            print("No local secrets.toml found. Checking environment...")
            return False

        if not creds_dict or not spreadsheet_id:
            print("Google Sheets credentials not configured")
            return False

        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        _gsheet_client = gspread.authorize(creds)

        # Open spreadsheet
        spreadsheet = _gsheet_client.open_by_key(spreadsheet_id)

        # Get or create alerts worksheet
        try:
            _gsheet_worksheet = spreadsheet.worksheet("alerts")
        except gspread.WorksheetNotFound:
            _gsheet_worksheet = spreadsheet.add_worksheet(title="alerts", rows=1000, cols=15)
            _gsheet_worksheet.append_row([
                'symbol', 'date', 'direction', 'score', 'alert_price',
                'criteria', 'pattern', 'combo', 'market', 'created_at'
            ])

        print("Connected to Google Sheets successfully!")
        return True

    except ImportError:
        print("gspread/toml not installed. Install with: pip install gspread google-auth toml")
        return False
    except Exception as e:
        print(f"Failed to connect to Google Sheets: {e}")
        return False


def load_history():
    """Load existing alert history from Google Sheets or local file."""
    global _gsheet_worksheet

    # Try Google Sheets first
    if _gsheet_worksheet:
        try:
            records = _gsheet_worksheet.get_all_records()
            print(f"Loaded {len(records)} existing alerts from Google Sheets")
            return records
        except Exception as e:
            print(f"Error loading from Google Sheets: {e}")

    # Fallback to local
    if not _HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(_HISTORY_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(history):
    """Save alert history to local JSON file (backup)."""
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE.write_text(
        json.dumps(history, default=str, indent=2),
        encoding='utf-8'
    )


def save_alerts_to_gsheet(alerts: list):
    """Save a batch of alerts to Google Sheets."""
    global _gsheet_worksheet

    if not _gsheet_worksheet or not alerts:
        return 0

    try:
        rows = []
        for alert in alerts:
            rows.append([
                alert.get('symbol', ''),
                alert.get('date', ''),
                alert.get('direction', ''),
                alert.get('score', 0),
                alert.get('alert_price', 0),
                alert.get('criteria', ''),
                alert.get('pattern', ''),
                alert.get('combo', ''),
                alert.get('market', 'us'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])

        _gsheet_worksheet.append_rows(rows)
        return len(rows)
    except Exception as e:
        print(f"Error saving to Google Sheets: {e}")
        return 0


def get_trading_days(start_date: str, end_date: str) -> list:
    """Get list of trading days between two dates using SPY as reference."""
    spy = yf.Ticker("SPY")
    hist = spy.history(start=start_date, end=end_date)
    return [d.strftime('%Y-%m-%d') for d in hist.index]


def fetch_historical_data(symbols: list, end_date: str, lookback_days: int = 100) -> dict:
    """Fetch historical data ending at a specific date."""
    end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    start = end - timedelta(days=lookback_days + 50)  # Extra buffer for weekends

    data = {}

    # Batch download for efficiency
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

                # Filter to only data up to end_date
                symbol_df = symbol_df[symbol_df.index <= end_date]

                if not symbol_df.empty and len(symbol_df) >= 20:
                    # Take last lookback_days
                    symbol_df = symbol_df.tail(lookback_days)
                    data[symbol] = symbol_df
            except Exception:
                continue

    except Exception as e:
        print(f"Error fetching batch data: {e}")

    return data


def backfill_market(market: str, start_date: str, end_date: str, min_score: int = 5, use_gsheet: bool = False):
    """Backfill alerts for a specific market."""
    print(f"\n{'='*60}")
    print(f"Backfilling {market.upper()} market from {start_date} to {end_date}")
    print(f"Storage: {'Google Sheets' if use_gsheet and _gsheet_worksheet else 'Local JSON'}")
    print(f"{'='*60}")

    # Get stock list
    if market == 'indian':
        symbols, _ = get_stock_list('indian', 'nifty200')
    else:
        symbols, _ = get_stock_list('us', 'sp500')

    print(f"Loaded {len(symbols)} symbols for {market.upper()}")

    # Get trading days
    print("Getting trading days...")
    if market == 'indian':
        # Use RELIANCE.NS as reference for Indian market
        try:
            ref = yf.Ticker("RELIANCE.NS")
            hist = ref.history(start=start_date, end=end_date)
            trading_days = [d.strftime('%Y-%m-%d') for d in hist.index]
        except:
            trading_days = get_trading_days(start_date, end_date)
    else:
        trading_days = get_trading_days(start_date, end_date)

    print(f"Found {len(trading_days)} trading days")

    # Load existing history
    history = load_history()
    existing_keys = {(a['symbol'], a['date'], a.get('market', 'us')) for a in history}

    total_new_alerts = 0
    pending_gsheet_alerts = []  # Buffer for batch saving to Google Sheets

    # Process each trading day
    for i, trade_date in enumerate(trading_days):
        print(f"\n[{i+1}/{len(trading_days)}] Processing {trade_date}...")

        # Fetch data up to this date
        daily_data = fetch_historical_data(symbols, trade_date, DEFAULT_LOOKBACK_DAYS)

        if not daily_data:
            print(f"  No data available for {trade_date}")
            continue

        print(f"  Loaded data for {len(daily_data)} stocks")

        # Generate alerts
        try:
            alerts_df = generate_alerts(daily_data, min_score=min_score)
        except Exception as e:
            print(f"  Error generating alerts: {e}")
            continue

        if alerts_df.empty:
            print(f"  No alerts with score >= {min_score}")
            continue

        # Save alerts
        new_count = 0
        for _, row in alerts_df.iterrows():
            symbol = row['Symbol']
            key = (symbol, trade_date, market)

            if key in existing_keys:
                continue

            # Get alert price (closing price on that day)
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

            # Add to Google Sheets buffer
            if use_gsheet and _gsheet_worksheet:
                pending_gsheet_alerts.append(alert_record)

        if new_count > 0:
            print(f"  + Added {new_count} alerts")
            total_new_alerts += new_count

            # Save periodically
            if i % 5 == 0:
                # Save to local JSON (backup)
                save_history(history)

                # Save to Google Sheets in batches
                if use_gsheet and pending_gsheet_alerts:
                    saved = save_alerts_to_gsheet(pending_gsheet_alerts)
                    print(f"  [Saved {saved} alerts to Google Sheets]")
                    pending_gsheet_alerts = []
                else:
                    print(f"  [Saved {len(history)} total alerts locally]")

        # Small delay to avoid rate limiting
        time.sleep(0.5)

    # Final save
    save_history(history)

    # Save remaining Google Sheets alerts
    if use_gsheet and pending_gsheet_alerts:
        saved = save_alerts_to_gsheet(pending_gsheet_alerts)
        print(f"[Final save: {saved} alerts to Google Sheets]")

    print(f"\n{'='*60}")
    print(f"COMPLETED {market.upper()}: Added {total_new_alerts} new alerts")
    print(f"Total alerts in history: {len(history)}")
    print(f"{'='*60}")

    return total_new_alerts


def main():
    """Main backfill function."""
    start_date = "2026-01-01"
    end_date = datetime.now().strftime('%Y-%m-%d')
    min_score = 5

    print("\n" + "="*60)
    print("ALERT BACKFILL SCRIPT")
    print(f"Period: {start_date} to {end_date}")
    print(f"Minimum Score: {min_score}")
    print("="*60)

    # Try to initialize Google Sheets
    use_gsheet = init_gsheet()
    if use_gsheet:
        print("Will save to Google Sheets + local backup")
    else:
        print("Will save to local JSON only")

    # Backfill US market
    us_count = backfill_market('us', start_date, end_date, min_score, use_gsheet)

    # Backfill Indian market
    indian_count = backfill_market('indian', start_date, end_date, min_score, use_gsheet)

    print("\n" + "="*60)
    print("BACKFILL COMPLETE")
    print(f"US Market: {us_count} alerts added")
    print(f"Indian Market: {indian_count} alerts added")
    print(f"Total: {us_count + indian_count} alerts added")
    if use_gsheet:
        print("Data saved to: Google Sheets + Local JSON")
    else:
        print("Data saved to: Local JSON only")
    print("="*60)


if __name__ == "__main__":
    main()
