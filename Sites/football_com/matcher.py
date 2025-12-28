"""
Matcher Module
Handles matching predictions.csv data with extracted Football.com matches using Gemini AI.
"""

import csv
import json
import re
import difflib
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from playwright.async_api import Page

from pathlib import Path
from Helpers.DB_Helpers.db_helpers import PREDICTIONS_CSV, update_prediction_status


async def filter_pending_predictions() -> List[Dict]:
    """Load and filter predictions that are pending booking."""
    pending_predictions = []
    csv_path = Path(PREDICTIONS_CSV)
    if csv_path.exists():
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            pending_predictions = [row for row in reader if row.get('status') == 'pending']
    print(f"  [Matcher] Found {len(pending_predictions)} pending predictions.")
    return pending_predictions


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity ratio between two strings."""
    return difflib.SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def parse_match_datetime(date_str: str, time_str: str, is_site_format: bool = False) -> Optional[datetime]:
    """
    Parse date and time strings into a datetime object.
    - Handles predictions.csv format: date='17.12.2025', time='20:30' (UTC)
    - Handles site format: date='17.12.2025', time='17 Dec, 20:30' (UTC+1 displayed)
    - Handles in-play site time like '59:51 H2' by returning None.
    Returns None if parsing fails.
    """
    if not date_str or not time_str:
        return None

    time_str = time_str.strip()
    date_str = date_str.strip()

    # For site format, extract time and use the provided date_str for the year
    if is_site_format:
        if ',' not in time_str:  # Handles in-play times or other non-standard formats
            return None
        try:
            # Site format: time_str = "17 Dec, 20:30"
            parts = time_str.split(',', 1)
            site_date_part = parts[0].strip() # "17 Dec"
            site_time_part = parts[1].strip() # "20:30"
            
            # Get year from the full date string provided from the site data
            year = datetime.strptime(date_str, "%d.%m.%Y").year
            
            dt_str = f"{site_date_part} {year} {site_time_part}"
            return datetime.strptime(dt_str, "%d %b %Y %H:%M")
        except (ValueError, IndexError):
            return None
    # For prediction format
    else:
        try:
            # Predictions format: date='17.12.2025', time='20:30'
            return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        except ValueError:
            # Fallback for other potential formats if needed in the future
            return None


async def match_predictions_with_site(day_predictions: List[Dict], site_matches: List[Dict]) -> Dict[str, str]:
    """
    Use fuzzy matching with priority on match datetime to match predictions with site matches.
    Predictions CSV datetime is in UTC.
    Betting site displays times in UTC+1.
    """
    # Filter out predictions for matches that have already started
    now_utc = datetime.utcnow()
    future_predictions = []
    for pred in day_predictions:
        pred_date = pred.get('date', '').strip()
        pred_time = pred.get('match_time', '').strip()
        pred_utc_dt = parse_match_datetime(pred_date, pred_time, is_site_format=False)
        # We add a 5 minute grace period to account for minor delays
        if pred_utc_dt and pred_utc_dt > (now_utc - timedelta(minutes=5)):
            future_predictions.append(pred)
    
    if not future_predictions:
        print("  [Matcher] All predictions are for matches that have already started.")
        return {}
        
    day_predictions = future_predictions
    
    print("  [Matcher] Fuzzy matching predictions to betting site matches (with datetime priority)...")
    if not day_predictions or not site_matches:
        return {}

    mapping = {}
    used_site_matches = set()

    for pred in day_predictions:
        pred_id = str(pred.get('fixture_id', ''))
        pred_home = pred.get('home_team', '').strip()
        pred_away = pred.get('away_team', '').strip()
        pred_league = pred.get('region_league', '').strip()

        # Parse prediction datetime (UTC)
        pred_date = pred.get('date', '').strip()
        pred_time = pred.get('match_time', '').strip() # FIX: was 'time'
        pred_utc_dt: Optional[datetime] = parse_match_datetime(pred_date, pred_time, is_site_format=False)

        best_match = None
        best_score = 0.0

        for site_match in site_matches:
            site_url = site_match.get('url', '')
            if site_url in used_site_matches:
                continue

            site_home = site_match.get('home', '').strip()
            site_away = site_match.get('away', '').strip()
            site_league = site_match.get('league', '').strip()

            # Parse site datetime (displayed as UTC+1)
            site_date = site_match.get('date', '').strip()
            site_time = site_match.get('time', '').strip()
            site_display_dt: Optional[datetime] = parse_match_datetime(site_date, site_time, is_site_format=True)

            # Convert site time (UTC+1) to UTC for comparison
            site_utc_dt: Optional[datetime] = (site_display_dt - timedelta(hours=1)) if site_display_dt else None

            # Calculate similarities
            home_sim = calculate_similarity(pred_home, site_home)
            away_sim = calculate_similarity(pred_away, site_away)
            league_sim = calculate_similarity(pred_league, site_league)

            # Base team + league score (lower weight to prioritize datetime)
            team_score = (home_sim + away_sim) / 2
            base_score = team_score * 0.6 + league_sim * 0.4  # 40% teams/league

            # Datetime matching priority
            time_bonus = 0.0
            if pred_utc_dt and site_utc_dt:
                time_diff = abs((pred_utc_dt - site_utc_dt).total_seconds())
                if time_diff <= 3600:  # Exact match (±60 minutes) - FIX: was 36000
                    time_bonus = 0.8
                elif time_diff <= 7200:  # Within 120 minutes for flexibility
                    time_bonus = 0.4

            total_score = base_score + time_bonus

            # Ensure a minimum team similarity before accepting a match, even with a time bonus
            if team_score > 0.4 and total_score > best_score and total_score > 0.6:
                best_score = total_score
                best_match = site_match

        # If a match was found
        if best_match:
            mapping[pred_id] = best_match.get('url', '')
            used_site_matches.add(best_match.get('url', ''))
            time_info = f" (UTC: {pred_utc_dt.strftime('%Y-%m-%d %H:%M') if pred_utc_dt else 'N/A'})"
            print(f"    Matched {pred_home} vs {pred_away}{time_info} -> {best_match.get('home', '')} vs {best_match.get('away', '')} (score: {best_score:.2f})")

    print(f"  [Matcher] Successfully matched {len(mapping)}/{len(day_predictions)} predictions.")
    return mapping
