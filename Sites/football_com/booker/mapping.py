"""
Market Mapping Logic
Translates prediction text into site-specific market and outcome names.
"""

import re
from typing import Dict

async def find_market_and_outcome(prediction: Dict) -> tuple:
    """Map prediction to market name and outcome name."""
    pred_text = prediction.get('prediction', '').strip()
    if not pred_text or pred_text == 'SKIP':
        return "", ""

    home_team = prediction.get('home_team', '').strip()
    away_team = prediction.get('away_team', '').strip()

    # Normalize strings
    pt_upper = pred_text.upper()
    ht_upper = home_team.upper()
    at_upper = away_team.upper()

    # --- 1. 1X2 (Match Winner) ---
    if pt_upper == "DRAW":
        return "1X2", "Draw"
    if pt_upper in [f"{ht_upper} TO WIN", f"{ht_upper} WIN", ht_upper, "1"]:
        return "1X2", "Home"
    if pt_upper in [f"{at_upper} TO WIN", f"{at_upper} WIN", at_upper, "2"]:
        return "1X2", "Away"
    if pt_upper == "X": return "1X2", "Draw"

    # --- 2. Double Chance ---
    if "OR DRAW" in pt_upper:
        if ht_upper in pt_upper: return "Double Chance", "Home or Draw"
        if at_upper in pt_upper: return "Double Chance", "Draw or Away"
    if f"{ht_upper} OR {at_upper}" in pt_upper or f"{at_upper} OR {ht_upper}" in pt_upper or pt_upper == "12":
        return "Double Chance", "Home or Away"
    if pt_upper == "1X": return "Double Chance", "Home or Draw"
    if pt_upper == "X2": return "Double Chance", "Draw or Away"

    # --- 3. Both Teams To Score ---
    if pt_upper in ["BTTS YES", "BTTS_YES"]: return "Both Teams To Score", "Yes"
    if pt_upper in ["BTTS NO", "BTTS_NO"]: return "Both Teams To Score", "No"

    # --- 4. Over/Under ---
    if ("OVER" in pt_upper or "UNDER" in pt_upper) and "&" not in pt_upper and "AND" not in pt_upper:
        match = re.search(r'(OVER|UNDER)[_\s]+(\d+\.5)', pt_upper)
        if match:
            line = match.group(2)
            type_str = match.group(1).title()
            return "Over/Under", f"{type_str} {line}"

    # --- 5. Draw No Bet ---
    if pt_upper == ht_upper: return "Draw No Bet", "Home"
    if pt_upper == at_upper: return "Draw No Bet", "Away"

    # --- 6. Goal Range ---
    if "GOALS" in pt_upper and "-" in pt_upper:
        range_val = pt_upper.replace("GOALS", "").strip()
        return "Goal Bounds", range_val

    return "", ""
