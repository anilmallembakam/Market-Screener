"""Google Sheets storage for alert history - persistent cloud storage."""
import json
import pandas as pd
import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional

# Google Sheets API
from google.oauth2.service_account import Credentials
import gspread

# Scopes for Google Sheets API
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Sheet names
ALERTS_SHEET = "alerts"
SCHEDULER_SHEET = "scheduler_state"


@st.cache_resource
def get_gsheet_client():
    """Get authenticated Google Sheets client using Streamlit secrets."""
    try:
        # Load credentials from Streamlit secrets
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None


def get_spreadsheet():
    """Get or create the alerts spreadsheet."""
    client = get_gsheet_client()
    if not client:
        return None

    try:
        # Try to open existing spreadsheet
        spreadsheet_id = st.secrets.get("spreadsheet_id", None)
        if spreadsheet_id:
            return client.open_by_key(spreadsheet_id)
        else:
            # Fallback to name
            return client.open("MarketScreenerAlerts")
    except gspread.SpreadsheetNotFound:
        # Create new spreadsheet
        spreadsheet = client.create("MarketScreenerAlerts")
        # Create alerts sheet with headers
        alerts_ws = spreadsheet.sheet1
        alerts_ws.update_title(ALERTS_SHEET)
        alerts_ws.append_row([
            'symbol', 'date', 'direction', 'score', 'alert_price',
            'criteria', 'pattern', 'combo', 'market', 'created_at'
        ])
        return spreadsheet
    except Exception as e:
        st.error(f"Error accessing spreadsheet: {e}")
        return None


def get_alerts_worksheet():
    """Get the alerts worksheet."""
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return None

    try:
        return spreadsheet.worksheet(ALERTS_SHEET)
    except gspread.WorksheetNotFound:
        # Create alerts worksheet
        ws = spreadsheet.add_worksheet(title=ALERTS_SHEET, rows=1000, cols=15)
        ws.append_row([
            'symbol', 'date', 'direction', 'score', 'alert_price',
            'criteria', 'pattern', 'combo', 'market', 'created_at'
        ])
        return ws


def load_history_gsheet() -> List[dict]:
    """Load alert history from Google Sheets."""
    ws = get_alerts_worksheet()
    if not ws:
        return []

    try:
        records = ws.get_all_records()
        return records
    except Exception as e:
        st.warning(f"Error loading from Google Sheets: {e}")
        return []


def save_alert_gsheet(alert: dict) -> bool:
    """Save a single alert to Google Sheets."""
    ws = get_alerts_worksheet()
    if not ws:
        return False

    try:
        row = [
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
        ]
        ws.append_row(row)
        return True
    except Exception as e:
        st.warning(f"Error saving to Google Sheets: {e}")
        return False


def save_alerts_batch_gsheet(alerts: List[dict]) -> int:
    """Save multiple alerts to Google Sheets. Returns count saved."""
    ws = get_alerts_worksheet()
    if not ws:
        return 0

    # Get existing alerts to check for duplicates
    existing = load_history_gsheet()
    existing_keys = {(a['symbol'], a['date']) for a in existing}

    rows_to_add = []
    for alert in alerts:
        key = (alert.get('symbol', ''), alert.get('date', ''))
        if key in existing_keys:
            continue  # Skip duplicate

        rows_to_add.append([
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

    if not rows_to_add:
        return 0

    try:
        ws.append_rows(rows_to_add)
        return len(rows_to_add)
    except Exception as e:
        st.warning(f"Error batch saving to Google Sheets: {e}")
        return 0


def delete_old_alerts_gsheet(days_to_keep: int = 60) -> int:
    """Delete alerts older than N days. Returns count deleted."""
    ws = get_alerts_worksheet()
    if not ws:
        return 0

    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')

    try:
        records = ws.get_all_records()
        rows_to_delete = []

        for i, record in enumerate(records, start=2):  # Start at 2 (row 1 is header)
            if record.get('date', '') < cutoff:
                rows_to_delete.append(i)

        # Delete from bottom to top to maintain row indices
        for row_idx in reversed(rows_to_delete):
            ws.delete_rows(row_idx)

        return len(rows_to_delete)
    except Exception as e:
        st.warning(f"Error deleting old alerts: {e}")
        return 0


def get_historical_alerts_gsheet(days_back: int = 30, market: str = None, direction: str = None) -> pd.DataFrame:
    """Get alerts from Google Sheets with optional filters."""
    from datetime import timedelta

    records = load_history_gsheet()
    if not records:
        return pd.DataFrame()

    cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

    filtered = [
        r for r in records
        if r.get('date', '') >= cutoff
    ]

    if market and market.lower() != 'all':
        filtered = [r for r in filtered if r.get('market', 'us').lower() == market.lower()]

    if direction and direction.lower() != 'all':
        filtered = [r for r in filtered if r.get('direction', '').lower() == direction.lower()]

    return pd.DataFrame(filtered) if filtered else pd.DataFrame()


def get_alerts_by_date_gsheet(date_str: str, market: str = None) -> pd.DataFrame:
    """Get alerts for a specific date."""
    records = load_history_gsheet()
    if not records:
        return pd.DataFrame()

    filtered = [r for r in records if r.get('date', '') == date_str]

    if market and market.lower() != 'all':
        filtered = [r for r in filtered if r.get('market', 'us').lower() == market.lower()]

    return pd.DataFrame(filtered) if filtered else pd.DataFrame()


def get_available_dates_gsheet() -> List[str]:
    """Get list of all dates that have alerts."""
    records = load_history_gsheet()
    if not records:
        return []

    dates = sorted(set(r.get('date', '') for r in records if r.get('date')), reverse=True)
    return dates


def is_gsheet_configured() -> bool:
    """Check if Google Sheets is properly configured."""
    try:
        return "gcp_service_account" in st.secrets
    except Exception:
        return False
