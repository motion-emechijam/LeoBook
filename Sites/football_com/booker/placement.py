"""
Bet Placement Orchestration
Handles adding selections to the slip and finalizing accumulators.
"""

import asyncio
from typing import List, Dict
from pathlib import Path
from datetime import datetime as dt
from playwright.async_api import Page
from Helpers.Site_Helpers.site_helpers import get_main_frame
from Helpers.DB_Helpers.db_helpers import update_prediction_status
from Helpers.utils import log_error_state
from Neo.selector_manager import SelectorManager
from Neo.intelligence import fb_universal_popup_dismissal as neo_popup_dismissal

from .ui import robust_click, handle_page_overlays, dismiss_overlays
from .mapping import find_market_and_outcome
from .slip import get_bet_slip_count

async def place_bets_for_matches(page: Page, matched_urls: Dict[str, str], day_predictions: List[Dict], target_date: str):
    """Visit matched URLs and place bets using prediction mappings."""
    selected_bets = 0
    processed_urls = set()
    MAX_BETS = 50

    for match_id, match_url in matched_urls.items():
        if await get_bet_slip_count(page) >= MAX_BETS:
            print(f"[Info] Slip full ({MAX_BETS}). Finalizing accumulator.")
            await finalize_accumulator(page, target_date)

        if not match_url or match_url in processed_urls: continue
        
        pred = next((p for p in day_predictions if str(p.get('fixture_id', '')) == str(match_id)), None)
        if not pred or pred.get('prediction') == 'SKIP': continue

        print(f"[Match Found] {pred['home_team']} vs {pred['away_team']}")
        processed_urls.add(match_url)

        try:
            if page.is_closed():
                print("  [Fatal] Page was closed before navigation. Aborting.")
                from playwright.async_api import Error as PlaywrightError
                raise PlaywrightError("Page closed before navigation")

            print(f"    [Nav] Navigating to match: {match_url}")
            await page.goto(match_url, wait_until='domcontentloaded', timeout=30000)

            if page.is_closed():
                print("  [Fatal] Page was closed immediately after navigation. Aborting.")
                from playwright.async_api import Error as PlaywrightError
                raise PlaywrightError("Page closed after navigation")

            await asyncio.sleep(5)
            await neo_popup_dismissal(page, match_url)

            # After successful navigation, get the main frame and place bets
            frame = await get_main_frame(page)
            if not frame:
                print(f"    [Error] Could not get main frame for {match_url}")
                update_prediction_status(match_id, target_date, 'dropped')
                continue

            m_name, o_name = await find_market_and_outcome(pred)
            if not m_name:
                print(f"    [Info] No market found for prediction: {pred.get('prediction', 'N/A')}")
                update_prediction_status(match_id, target_date, 'dropped')
                continue

            print(f"    [Betting] Looking for market '{m_name}' with outcome '{o_name}'")

            # Find and click search icon using priority-based selectors
            search_selectors = [
                ".search-icon",                      # Football.com search icon
                "[class*='search'] svg",           # Icon in search container
                "svg[viewBox*='24']",              # Common search icon viewBox
                "[data-op*='search']",             # Data attribute
                "button:has(svg)",                 # Button containing SVG
            ]

            search_clicked = False
            for search_sel in search_selectors:
                try:
                    if await frame.locator(search_sel).count() > 0:
                        await frame.locator(search_sel).first.click()
                        print(f"    [Betting] Clicked search with selector: {search_sel}")
                        search_clicked = True
                        await asyncio.sleep(1)
                        break
                except Exception as e:
                    print(f"    [Betting] Search selector failed: {search_sel} - {e}")
                    continue

            if not search_clicked:
                print("    [Betting] Could not find search icon")
                continue

            # Find and fill search input using priority-based selectors
            input_selectors = [
                "input.searchMode",                # Football.com search input
                ".searchMode input",              # Input in search mode
                "input[type='text']",             # Generic text input
                "input[placeholder*='search']",   # Placeholder-based
                "input.full-size",                # Football.com specific class
            ]

            input_found = False
            for input_sel in input_selectors:
                try:
                    if await frame.locator(input_sel).count() > 0:
                        await frame.locator(input_sel).first.fill(m_name)
                        print(f"    [Betting] Filled search input with selector: {input_sel}")
                        input_found = True
                        await asyncio.sleep(2)
                        break
                except Exception as e:
                    print(f"    [Betting] Input selector failed: {input_sel} - {e}")
                    continue

            if not input_found:
                print("    [Betting] Could not find search input")
                continue

            # Select Outcome using priority-based selectors
            outcome_selectors = [
                f"div.m-table-row > div:has-text('{o_name}')",  # Football.com specific
                f"[class*='outcome']:has-text('{o_name}')",     # Generic outcome with text
                f"div:has-text('{o_name}')",                    # Any div with the outcome text
                f"button:has-text('{o_name}')",                 # Button with outcome text
                f"span:has-text('{o_name}')",                   # Span with outcome text
            ]

            bet_selected = False
            for outcome_sel in outcome_selectors:
                try:
                    if await frame.locator(outcome_sel).count() > 0:
                        count_before = await get_bet_slip_count(page)
                        if await robust_click(frame.locator(outcome_sel).first, page):
                            await asyncio.sleep(2)
                            if await get_bet_slip_count(page) > count_before:
                                selected_bets += 1
                                update_prediction_status(match_id, target_date, 'booked')
                                print(f"    [Success] Added bet for {pred['home_team']} vs {pred['away_team']}")
                                bet_selected = True
                                break
                except Exception as e:
                    print(f"    [Betting] Outcome selector failed: {outcome_sel} - {e}")
                    continue

            if bet_selected:
                continue

            print(f"    [Info] Could not place bet for {pred['home_team']} vs {pred['away_team']}")
            update_prediction_status(match_id, target_date, 'dropped')

        except Exception as e:
            print(f"    [Error] Match failed: {e}")
            # Check for Playwright-specific errors indicating page/browser closure
            from playwright.async_api import Error as PlaywrightError
            error_msg = str(e).lower()
            is_closure_error = (
                "target closed" in error_msg or 
                "browser has been closed" in error_msg or 
                "context was closed" in error_msg or
                "page has been closed" in error_msg
            )
            if is_closure_error or isinstance(e, PlaywrightError):
                print("    [Fatal] Browser or Page closed during betting loop. Aborting.")
                raise e

    print(f"  [Summary] Selected {selected_bets} bets for {target_date}.")
    if await get_bet_slip_count(page) > 0:
        await finalize_accumulator(page, target_date)

async def finalize_accumulator(page: Page, target_date: str) -> bool:
    """Navigate to slip, enter stake, and confirm placement."""
    print(f"[Betting] Finalizing accumulator for {target_date}...")
    try:
        await dismiss_overlays(page)
        await handle_page_overlays(page)
        # Refresh state after dismissals
        await asyncio.sleep(1)
        await page.keyboard.press("End")
        
        is_open_selectors = ["div[data-op='betslip-container']", ".bottom-panel-drawer", "div.m-betslip-place-bet"]
        is_open = any([await page.locator(s).first.is_visible(timeout=500) for s in is_open_selectors])

        if not is_open:
            triggers = ["div[data-op='betslip-multi-min-count']", ".open-bet-icon", "text='Betslip'"]
            for t in triggers:
                if await robust_click(page.locator(t).first, page):
                    await asyncio.sleep(3)
                    break

        # Ensure 'Multiple' tab is selected for accumulators
        multi_tab = "div.m-betslip-tab-item:has-text('Multiple'), .m-betslip-tabs > div:nth-child(2)"
        if await page.locator(multi_tab).count() > 0:
            if await page.locator(multi_tab).is_visible(timeout=2000):
                await page.locator(multi_tab).click()
                await asyncio.sleep(1)

        # Enter Stake using priority-based selectors
        stake_selectors = [
            "input[type='number']",               # Standard number input
            ".m-betslip-stake-input",            # Football.com stake input
            "[placeholder*='stake']",            # Placeholder-based
            "[class*='stake'] input",            # Class-based
            ".stake-input",                      # Generic stake class
        ]

        stake_entered = False
        for stake_sel in stake_selectors:
            try:
                if await page.locator(stake_sel).count() > 0:
                    input_field = page.locator(stake_sel).first
                    await input_field.click()
                    await input_field.fill("1")
                    await page.keyboard.press("Enter")
                    print(f"    [Betting] Entered stake with selector: {stake_sel}")
                    stake_entered = True
                    await asyncio.sleep(1)
                    break
            except Exception as e:
                print(f"    [Betting] Stake selector failed: {stake_sel} - {e}")
                continue

        if not stake_entered:
            print("    [Warning] Could not enter stake. Attempting to place anyway.")

        # Place bet using priority-based selectors
        place_selectors = [
            "div[data-op='place-bet']",           # Football.com place bet
            ".m-place-bet-btn",                  # Football.com button class
            "button:has-text('Place')",          # Text-based
            "[class*='place'] button",           # Class-based
            ".place-bet",                        # Generic class
        ]

        bet_placed = False
        for place_sel in place_selectors:
            try:
                if await robust_click(page.locator(place_sel).first, page):
                    print(f"    [Betting] Clicked place bet with selector: {place_sel}")
                    bet_placed = True
                    await asyncio.sleep(2)
                    break
            except Exception as e:
                print(f"    [Betting] Place bet selector failed: {place_sel} - {e}")
                continue

        if not bet_placed:
            print("    [Betting] Could not place bet")
            return False

        # Confirm bet using priority-based selectors
        confirm_selectors = [
            "button:has-text('Confirm')",         # Text-based
            ".m-confirm-btn",                    # Football.com confirm class
            "[data-op='confirm']",               # Data attribute
            ".confirm-button",                   # Generic class
            ".btn-confirm",                      # Alternative class
        ]

        for confirm_sel in confirm_selectors:
            try:
                if await page.locator(confirm_sel).count() > 0:
                    await robust_click(page.locator(confirm_sel).first, page)
                    print(f"    [Betting] Confirmed bet with selector: {confirm_sel}")
                    await asyncio.sleep(3)
                    
                    # Extract and save booking code
                    booking_code = await extract_booking_details(page)
                    if booking_code and booking_code != "N/A":
                        await save_booking_code(target_date, booking_code, page)
                    
                    print(f"    [Success] Placed for {target_date}")
                    return True
            except Exception as e:
                print(f"    [Betting] Confirm selector failed: {confirm_sel} - {e}")
                continue

        print("    [Betting] Could not confirm bet")
        return False
    except Exception as e:
        await log_error_state(page, "finalize_fatal", e)
    return False

async def extract_booking_details(page: Page) -> str:
    """Extract booking code using priority-based selectors."""
    code_selectors = [
        ".bet-code",                          # Football.com bet code class
        "[class*='code']",                    # Generic code class
        "[data-op*='code']",                  # Data attribute
        "span:not(.divider)",                 # Football.com specific format
        ".booking-code",                      # Alternative class
    ]

    for code_sel in code_selectors:
        try:
            if await page.locator(code_sel).count() > 0:
                code = await page.locator(code_sel).first.inner_text()
                if code and code.strip():
                    print(f"    [Booking] Code: {code.strip()}")
                    return code.strip()
        except Exception as e:
            print(f"    [Booking] Code selector failed: {code_sel} - {e}")
            continue

    print("    [Booking] Could not extract booking code")
    return "N/A"


async def save_booking_code(target_date: str, booking_code: str, page: Page):
    """
    Save booking code to file and capture betslip screenshot.
    Stores in DB/bookings.txt with timestamp and date association.
    """
    from pathlib import Path
    
    try:
        # Save to bookings file
        db_dir = Path("DB")
        db_dir.mkdir(exist_ok=True)
        bookings_file = db_dir / "bookings.txt"
        
        timestamp = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        booking_entry = f"{timestamp} | Date: {target_date} | Code: {booking_code}\n"
        
        with open(bookings_file, "a", encoding="utf-8") as f:
            f.write(booking_entry)
        
        print(f"    [Booking] Saved code {booking_code} to bookings.txt")
        
        # Capture betslip screenshot for records
        try:
            screenshot_path = db_dir / f"betslip_{booking_code}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"    [Booking] Saved screenshot to {screenshot_path.name}")
        except Exception as screenshot_error:
            print(f"    [Booking] Screenshot failed: {screenshot_error}")
            
    except Exception as e:
        print(f"    [Booking] Failed to save booking code: {e}")

