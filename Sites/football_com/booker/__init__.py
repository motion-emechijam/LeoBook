"""
Booker Package
Exposes core modules for UI, Mapping, Slip, and Placement.
"""

from .ui import handle_page_overlays, robust_click, dismiss_overlays, wait_for_element
from .mapping import find_market_and_outcome
from .slip import get_bet_slip_count, clear_bet_slip
from .placement import place_bets_for_matches, finalize_accumulator, extract_booking_details

__all__ = [
    'handle_page_overlays',
    'robust_click',
    'dismiss_overlays',
    'wait_for_element',
    'find_market_and_outcome',
    'get_bet_slip_count',
    'clear_bet_slip',
    'place_bets_for_matches',
    'finalize_accumulator',
    'extract_booking_details'
]
