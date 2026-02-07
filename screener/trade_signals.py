import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from screener.market_mood import get_cached_scores
from screener.technical_indicators import compute_all
from screener.support_resistance import detect_levels
from screener.config import NIFTY_STRIKE_STEP, BANKNIFTY_STRIKE_STEP


# Sector mapping for Indian stocks (Nifty 200)
SECTOR_MAP = {
    # Financials
    'HDFCBANK.NS': 'Financials', 'ICICIBANK.NS': 'Financials',
    'SBIN.NS': 'Financials', 'KOTAKBANK.NS': 'Financials',
    'AXISBANK.NS': 'Financials', 'BAJFINANCE.NS': 'Financials',
    'BAJAJFINSV.NS': 'Financials', 'INDUSINDBK.NS': 'Financials',
    'BANDHANBNK.NS': 'Financials', 'HDFCLIFE.NS': 'Financials',
    'SBILIFE.NS': 'Financials', 'HDFCAMC.NS': 'Financials',
    'ICICIGI.NS': 'Financials', 'ICICIPRULI.NS': 'Financials',
    'SBICARD.NS': 'Financials', 'CHOLAFIN.NS': 'Financials',
    'MFSL.NS': 'Financials', 'SHRIRAMFIN.NS': 'Financials',
    'PFC.NS': 'Financials', 'RECLTD.NS': 'Financials',
    'BANKBARODA.NS': 'Financials', 'PNB.NS': 'Financials',
    'FEDERALBNK.NS': 'Financials', 'IDFCFIRSTB.NS': 'Financials',
    'CANBK.NS': 'Financials', 'LICHSGFIN.NS': 'Financials',
    'M&MFIN.NS': 'Financials', 'MANAPPURAM.NS': 'Financials',
    'MUTHOOTFIN.NS': 'Financials', 'AUBANK.NS': 'Financials',
    # IT
    'TCS.NS': 'IT', 'INFY.NS': 'IT', 'HCLTECH.NS': 'IT',
    'WIPRO.NS': 'IT', 'TECHM.NS': 'IT', 'LTIM.NS': 'IT',
    'LTTS.NS': 'IT', 'MPHASIS.NS': 'IT', 'COFORGE.NS': 'IT',
    'PERSISTENT.NS': 'IT', 'TATAELXSI.NS': 'IT',
    # Pharma & Healthcare
    'SUNPHARMA.NS': 'Pharma', 'DRREDDY.NS': 'Pharma',
    'CIPLA.NS': 'Pharma', 'DIVISLAB.NS': 'Pharma',
    'APOLLOHOSP.NS': 'Pharma', 'BIOCON.NS': 'Pharma',
    'LUPIN.NS': 'Pharma', 'AUROPHARMA.NS': 'Pharma',
    'TORNTPHARM.NS': 'Pharma', 'IPCALAB.NS': 'Pharma',
    'LALPATHLAB.NS': 'Pharma', 'GLENMARK.NS': 'Pharma',
    'ZYDUSLIFE.NS': 'Pharma',
    # Auto
    'TATAMOTORS.NS': 'Auto', 'M&M.NS': 'Auto', 'MARUTI.NS': 'Auto',
    'BAJAJ-AUTO.NS': 'Auto', 'EICHERMOT.NS': 'Auto',
    'HEROMOTOCO.NS': 'Auto', 'TVSMOTOR.NS': 'Auto',
    'ESCORTS.NS': 'Auto', 'BHARATFORG.NS': 'Auto',
    'MOTHERSON.NS': 'Auto',
    # Metals & Mining
    'TATASTEEL.NS': 'Metals', 'JSWSTEEL.NS': 'Metals',
    'HINDALCO.NS': 'Metals', 'VEDL.NS': 'Metals',
    'COALINDIA.NS': 'Metals', 'NMDC.NS': 'Metals',
    'SAIL.NS': 'Metals', 'JINDALSTEL.NS': 'Metals',
    'NATIONALUM.NS': 'Metals', 'HINDCOPPER.NS': 'Metals',
    # Energy & Power
    'RELIANCE.NS': 'Energy', 'ONGC.NS': 'Energy',
    'BPCL.NS': 'Energy', 'IOC.NS': 'Energy',
    'HINDPETRO.NS': 'Energy', 'GAIL.NS': 'Energy',
    'NTPC.NS': 'Energy', 'POWERGRID.NS': 'Energy',
    'TATAPOWER.NS': 'Energy', 'ADANIGREEN.NS': 'Energy',
    'ADANIENT.NS': 'Energy', 'JSWENERGY.NS': 'Energy',
    'PETRONET.NS': 'Energy', 'IGL.NS': 'Energy',
    # FMCG
    'HINDUNILVR.NS': 'FMCG', 'ITC.NS': 'FMCG',
    'NESTLEIND.NS': 'FMCG', 'BRITANNIA.NS': 'FMCG',
    'TATACONSUM.NS': 'FMCG', 'DABUR.NS': 'FMCG',
    'GODREJCP.NS': 'FMCG', 'MARICO.NS': 'FMCG',
    'COLPAL.NS': 'FMCG',
    # Infra & Cement
    'LT.NS': 'Infra', 'ADANIPORTS.NS': 'Infra',
    'DLF.NS': 'Infra', 'GODREJPROP.NS': 'Infra',
    'ULTRACEMCO.NS': 'Infra', 'SHREECEM.NS': 'Infra',
    'AMBUJACEM.NS': 'Infra', 'SIEMENS.NS': 'Infra',
    'IRCTC.NS': 'Infra',
    # Telecom
    'BHARTIARTL.NS': 'Telecom', 'IDEA.NS': 'Telecom',
    'INDUSTOWER.NS': 'Telecom',
    # Consumer & Retail
    'TITAN.NS': 'Consumer', 'ASIANPAINT.NS': 'Consumer',
    'PIDILITIND.NS': 'Consumer', 'HAVELLS.NS': 'Consumer',
    'VOLTAS.NS': 'Consumer', 'TRENT.NS': 'Consumer',
    'JUBLFOOD.NS': 'Consumer', 'DIXON.NS': 'Consumer',
    'POLYCAB.NS': 'Consumer',
    # Chemicals
    'SRF.NS': 'Chemicals', 'PIIND.NS': 'Chemicals',
    'DEEPAKNTR.NS': 'Chemicals', 'NAVINFLUOR.NS': 'Chemicals',
    'TATACHEM.NS': 'Chemicals', 'UPL.NS': 'Chemicals',
    # Defence
    'HAL.NS': 'Defence', 'BEL.NS': 'Defence',
}


def get_index_strategy_signal(
    index_name: str,
    current_price: float,
    max_pain: float,
    pcr_oi: float,
    vix: Optional[float],
    highest_call_oi_strike: float,
    highest_put_oi_strike: float,
) -> dict:
    reasoning = []
    risk_level = "Medium"

    # Determine strike step
    if 'BANK' in index_name.upper():
        step = BANKNIFTY_STRIKE_STEP
    else:
        step = NIFTY_STRIKE_STEP

    # Distance from max pain
    distance_pct = abs(current_price - max_pain) / max_pain * 100 if max_pain > 0 else 0
    reasoning.append(
        f"Spot: {current_price:.0f}, Max Pain: {max_pain:.0f} "
        f"(distance: {distance_pct:.1f}%)"
    )

    # PCR interpretation
    if pcr_oi > 1.3:
        pcr_bias = "bullish"
        reasoning.append(f"PCR (OI): {pcr_oi:.3f} -- heavy put writing, bullish support")
    elif pcr_oi < 0.7:
        pcr_bias = "bearish"
        reasoning.append(f"PCR (OI): {pcr_oi:.3f} -- low PCR, bearish bias")
    else:
        pcr_bias = "neutral"
        reasoning.append(f"PCR (OI): {pcr_oi:.3f} -- neutral range")

    # VIX
    if vix is not None:
        reasoning.append(f"VIX: {vix:.2f}")
        if vix > 20:
            vix_regime = "high"
            risk_level = "High"
        elif vix < 13:
            vix_regime = "low"
        else:
            vix_regime = "normal"
    else:
        vix_regime = "unknown"

    # OI range
    if highest_put_oi_strike > 0 and highest_call_oi_strike > 0:
        reasoning.append(
            f"OI Range: {highest_put_oi_strike:.0f} (Put support) - "
            f"{highest_call_oi_strike:.0f} (Call resistance)"
        )

    # Strategy decision tree
    atm = round(current_price / step) * step

    if distance_pct < 1.5 and vix_regime in ("normal", "low") and pcr_bias == "neutral":
        strategy = "Short Straddle"
        strikes = f"ATM: {atm}"
        risk_level = "Low" if vix_regime == "low" else "Medium"
        reasoning.append("Price near Max Pain + neutral PCR = range-bound expected")

    elif distance_pct < 3.0 and vix_regime == "normal":
        strategy = "Short Strangle"
        strikes = f"PE: {highest_put_oi_strike:.0f}, CE: {highest_call_oi_strike:.0f}"
        reasoning.append("Moderate distance from Max Pain -- wider strikes safer")

    elif vix_regime == "high":
        strategy = "Iron Condor"
        inner_put = highest_put_oi_strike if highest_put_oi_strike > 0 else atm - step
        inner_call = highest_call_oi_strike if highest_call_oi_strike > 0 else atm + step
        strikes = (f"Sell PE {inner_put:.0f} / Buy PE {inner_put - step:.0f}, "
                   f"Sell CE {inner_call:.0f} / Buy CE {inner_call + step:.0f}")
        reasoning.append("High VIX -- defined-risk Iron Condor preferred")

    elif pcr_bias == "bullish" and distance_pct > 2:
        strategy = "Directional (CE Buy)"
        strikes = f"ATM CE: {atm} or ITM CE: {atm - step}"
        reasoning.append("Strong put support + bullish bias -- buy calls")

    elif pcr_bias == "bearish" and distance_pct > 2:
        strategy = "Directional (PE Buy)"
        strikes = f"ATM PE: {atm} or ITM PE: {atm + step}"
        reasoning.append("Bearish PCR + weak support -- buy puts")

    else:
        strategy = "Short Straddle"
        strikes = f"ATM: {atm}"
        reasoning.append("Default: neutral conditions favor ATM straddle")

    return {
        'strategy': strategy,
        'underlying': index_name,
        'strikes': strikes,
        'risk_level': risk_level,
        'reasoning': reasoning,
    }


def _find_option(chain: pd.DataFrame, target_strike: float) -> dict:
    """Find the nearest option to target_strike and return its details."""
    if chain.empty:
        return {'strike': target_strike, 'ltp': 0, 'iv': 0, 'oi': 0, 'bid': 0, 'ask': 0}
    clean = chain.dropna(subset=['strike'])
    if clean.empty:
        return {'strike': target_strike, 'ltp': 0, 'iv': 0, 'oi': 0, 'bid': 0, 'ask': 0}
    idx = (clean['strike'] - target_strike).abs().argsort().iloc[0]
    row = clean.iloc[idx]
    return {
        'strike': float(row['strike']),
        'ltp': round(float(row.get('lastPrice', 0) or 0), 2),
        'iv': round(float(row.get('impliedVolatility', 0) or 0) * 100, 1),
        'oi': int(row.get('openInterest', 0) or 0),
        'bid': round(float(row.get('bid', 0) or 0), 2),
        'ask': round(float(row.get('ask', 0) or 0), 2),
    }


def build_strike_details(
    strategy: str,
    current_price: float,
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    expiries: list,
    selected_expiry: str,
    step: int,
    highest_call_oi_strike: float = 0,
    highest_put_oi_strike: float = 0,
) -> dict:
    """Build detailed strike recommendations with LTP, IV, OI for each leg."""
    atm = round(current_price / step) * step
    legs = []
    total_premium = 0.0

    if strategy == "Short Straddle":
        ce = _find_option(calls, atm)
        pe = _find_option(puts, atm)
        legs = [
            {**ce, 'leg': 'Leg 1', 'action': 'SELL', 'type': 'CE'},
            {**pe, 'leg': 'Leg 2', 'action': 'SELL', 'type': 'PE'},
        ]
        total_premium = ce['ltp'] + pe['ltp']
        be_upper = atm + total_premium
        be_lower = atm - total_premium
        max_profit = f"{total_premium:.2f} (premium collected)"
        max_loss = "Unlimited"

    elif strategy == "Short Strangle":
        ce_strike = highest_call_oi_strike if highest_call_oi_strike > 0 else atm + step
        pe_strike = highest_put_oi_strike if highest_put_oi_strike > 0 else atm - step
        ce = _find_option(calls, ce_strike)
        pe = _find_option(puts, pe_strike)
        legs = [
            {**ce, 'leg': 'Leg 1', 'action': 'SELL', 'type': 'CE'},
            {**pe, 'leg': 'Leg 2', 'action': 'SELL', 'type': 'PE'},
        ]
        total_premium = ce['ltp'] + pe['ltp']
        be_upper = ce['strike'] + total_premium
        be_lower = pe['strike'] - total_premium
        max_profit = f"{total_premium:.2f} (premium collected)"
        max_loss = "Unlimited"

    elif strategy == "Iron Condor":
        inner_ce = highest_call_oi_strike if highest_call_oi_strike > 0 else atm + step
        inner_pe = highest_put_oi_strike if highest_put_oi_strike > 0 else atm - step
        outer_ce = inner_ce + step
        outer_pe = inner_pe - step

        sell_ce = _find_option(calls, inner_ce)
        buy_ce = _find_option(calls, outer_ce)
        sell_pe = _find_option(puts, inner_pe)
        buy_pe = _find_option(puts, outer_pe)

        legs = [
            {**sell_pe, 'leg': 'Leg 1', 'action': 'SELL', 'type': 'PE'},
            {**buy_pe, 'leg': 'Leg 2', 'action': 'BUY', 'type': 'PE'},
            {**sell_ce, 'leg': 'Leg 3', 'action': 'SELL', 'type': 'CE'},
            {**buy_ce, 'leg': 'Leg 4', 'action': 'BUY', 'type': 'CE'},
        ]
        credit = (sell_ce['ltp'] + sell_pe['ltp']) - (buy_ce['ltp'] + buy_pe['ltp'])
        total_premium = round(credit, 2)
        spread_width = step
        max_loss_val = spread_width - abs(total_premium)
        be_upper = sell_ce['strike'] + abs(total_premium)
        be_lower = sell_pe['strike'] - abs(total_premium)
        max_profit = f"{abs(total_premium):.2f} (net credit)"
        max_loss = f"{max_loss_val:.2f} (spread width - premium)"

    elif "CE Buy" in strategy:
        atm_ce = _find_option(calls, atm)
        itm_ce = _find_option(calls, atm - step)
        legs = [
            {**atm_ce, 'leg': 'ATM', 'action': 'BUY', 'type': 'CE'},
            {**itm_ce, 'leg': 'ITM (alt)', 'action': 'BUY', 'type': 'CE'},
        ]
        total_premium = atm_ce['ltp']  # premium paid (stored as positive)
        be_upper = atm_ce['strike'] + atm_ce['ltp']
        be_lower = atm_ce['strike']
        max_profit = "Unlimited"
        max_loss = f"{atm_ce['ltp']:.2f} (premium paid)"

    elif "PE Buy" in strategy:
        atm_pe = _find_option(puts, atm)
        itm_pe = _find_option(puts, atm + step)
        legs = [
            {**atm_pe, 'leg': 'ATM', 'action': 'BUY', 'type': 'PE'},
            {**itm_pe, 'leg': 'ITM (alt)', 'action': 'BUY', 'type': 'PE'},
        ]
        total_premium = atm_pe['ltp']  # premium paid (stored as positive)
        be_upper = atm_pe['strike']
        be_lower = atm_pe['strike'] - atm_pe['ltp']
        max_profit = "Unlimited (to downside)"
        max_loss = f"{atm_pe['ltp']:.2f} (premium paid)"

    else:
        # Fallback: ATM straddle
        ce = _find_option(calls, atm)
        pe = _find_option(puts, atm)
        legs = [
            {**ce, 'leg': 'Leg 1', 'action': 'SELL', 'type': 'CE'},
            {**pe, 'leg': 'Leg 2', 'action': 'SELL', 'type': 'PE'},
        ]
        total_premium = ce['ltp'] + pe['ltp']
        be_upper = atm + total_premium
        be_lower = atm - total_premium
        max_profit = f"{total_premium:.2f} (premium collected)"
        max_loss = "Unlimited"

    return {
        'recommended_expiry': selected_expiry,
        'all_expiries': expiries,
        'legs': legs,
        'total_premium': round(total_premium, 2),
        'max_profit': max_profit,
        'max_loss': max_loss,
        'breakeven_upper': round(be_upper, 2),
        'breakeven_lower': round(be_lower, 2),
    }


def get_momentum_picks(data: Dict[str, pd.DataFrame],
                       top_n: int = 5) -> Tuple[List[dict], List[dict]]:
    scores = get_cached_scores(data)
    scored = []

    for sym, df in data.items():
        if len(df) < 50:
            continue
        result = scores.get(sym)
        if not result:
            continue
        try:
            enriched = compute_all(df.copy())
            last = enriched.iloc[-1]
            close = float(last['Close'])

            vol_ratio = last.get('Volume_Ratio', np.nan)
            has_volume = pd.notna(vol_ratio) and vol_ratio > 1.0

            resistance, support, _ = detect_levels(df)
            nearest_support = max([s for s in support if s < close], default=close * 0.97)
            nearest_resistance = min([r for r in resistance if r > close], default=close * 1.03)

            criteria_str = ', '.join(c['criterion'] for c in result['criteria'][:3])

            scored.append({
                'symbol': sym,
                'bullish_score': result['bullish_score'],
                'bearish_score': result['bearish_score'],
                'has_volume': has_volume,
                'close': round(close, 2),
                'criteria_summary': criteria_str,
                'support': round(nearest_support, 2),
                'resistance': round(nearest_resistance, 2),
            })
        except Exception:
            continue

    bullish = sorted(
        [s for s in scored if s['bullish_score'] > s['bearish_score']],
        key=lambda x: (x['bullish_score'], x['has_volume']),
        reverse=True,
    )[:top_n]

    bearish = sorted(
        [s for s in scored if s['bearish_score'] > s['bullish_score']],
        key=lambda x: (x['bearish_score'], x['has_volume']),
        reverse=True,
    )[:top_n]

    def fmt(p, direction):
        score = p['bullish_score'] if direction == 'bullish' else p['bearish_score']
        return {
            'symbol': p['symbol'], 'score': score, 'direction': direction,
            'criteria': p['criteria_summary'], 'close': p['close'],
            'support': p['support'], 'resistance': p['resistance'],
        }

    return ([fmt(p, 'bullish') for p in bullish],
            [fmt(p, 'bearish') for p in bearish])


def compute_sector_heatmap(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    scores = get_cached_scores(data)
    sector_data = {}

    for sym, df in data.items():
        sector = SECTOR_MAP.get(sym, 'Other')
        result = scores.get(sym)
        if not result:
            continue
        net = result['bullish_score'] - result['bearish_score']
        if sector not in sector_data:
            sector_data[sector] = {'bulls': 0, 'bears': 0, 'nets': [], 'count': 0}
        sector_data[sector]['count'] += 1
        sector_data[sector]['nets'].append(net)
        if result['bullish_score'] > result['bearish_score']:
            sector_data[sector]['bulls'] += 1
        elif result['bearish_score'] > result['bullish_score']:
            sector_data[sector]['bears'] += 1

    rows = []
    for sector, info in sector_data.items():
        if info['count'] == 0 or sector == 'Other':
            continue
        rows.append({
            'Sector': sector,
            'Bullish': info['bulls'],
            'Bearish': info['bears'],
            'Count': info['count'],
            'Avg Net Score': round(float(np.mean(info['nets'])), 2),
        })

    df_out = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['Sector', 'Bullish', 'Bearish', 'Count', 'Avg Net Score'])
    if not df_out.empty:
        df_out = df_out.sort_values('Avg Net Score', ascending=False).reset_index(drop=True)
    return df_out
