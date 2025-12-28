"""
Betslip Management
Handles counting and clearing of the betslip.
"""

import re
import asyncio
from playwright.async_api import Page
from .ui import robust_click
from Neo.selector_manager import SelectorManager

async def get_bet_slip_count(page: Page) -> int:
    """Extract current number of bets in the slip using priority-based selectors."""
    count_selectors = [
        ".open-bet-icon + .circle",           # Football.com bet counter badge
        "[class*='bet'] [class*='count']",    # Generic bet count
        ".betslip-count",                     # Alternative count class
        "[data-count]",                       # Data attribute with count
        ".bet-counter",                       # Generic counter
    ]

    for count_sel in count_selectors:
        try:
            if await page.locator(count_sel).count() > 0:
                text = await page.locator(count_sel).first.inner_text(timeout=2000)
                count = int(re.sub(r'\D', '', text) or 0)
                if count > 0:
                    return count
        except Exception as e:
            print(f"    [Slip] Count selector failed: {count_sel} - {e}")
            continue

    return 0

async def clear_bet_slip(page: Page):
    """Ensure the bet slip is empty before starting a new session using priority-based selectors."""
    print("    [Slip] Checking if bet slip needs clearing...")
    try:
        if await get_bet_slip_count(page) > 0:
            print("    [Slip] Bets detected. Opening slip to clear...")

            # Open bet slip using priority-based selectors
            open_selectors = [
                ".open-bet-icon",                    # Football.com bet slip trigger
                "[class*='bet'] [class*='icon']",    # Generic bet icon
                "[data-op*='betslip']",              # Data attribute
                ".bet-slip-toggle",                  # Generic toggle
                "text='Betslip'",                    # Text fallback
            ]

            slip_opened = False
            for open_sel in open_selectors:
                try:
                    if await page.locator(open_sel).count() > 0:
                        await robust_click(page.locator(open_sel).first, page)
                        print(f"    [Slip] Opened bet slip with selector: {open_sel}")
                        slip_opened = True
                        await asyncio.sleep(2)
                        break
                except Exception as e:
                    print(f"    [Slip] Open selector failed: {open_sel} - {e}")
                    continue

            if not slip_opened:
                print("    [Slip] Could not open bet slip")
                return

            # Clear all bets using priority-based selectors
            clear_selectors = [
                ".m-icon-delete",                    # Football.com delete icon
                "[class*='clear']",                  # Generic clear class
                "[data-op*='clear']",                # Data attribute
                "text='Clear All'",                  # Text-based
                ".clear-all",                        # Generic class
            ]

            bets_cleared = False
            for clear_sel in clear_selectors:
                try:
                    if await page.locator(clear_sel).count() > 0:
                        await page.locator(clear_sel).first.click()
                        print(f"    [Slip] Clicked clear with selector: {clear_sel}")
                        bets_cleared = True
                        await asyncio.sleep(1)

                        # Confirm clear action if confirmation appears
                        confirm_selectors = [
                            "button:has-text('Confirm')",     # Text-based
                            ".m-confirm-btn",                # Football.com confirm
                            "[data-op='confirm']",           # Data attribute
                            ".confirm-clear",                # Generic class
                        ]

                        for confirm_sel in confirm_selectors:
                            try:
                                if await page.locator(confirm_sel).count() > 0:
                                    await page.locator(confirm_sel).first.click()
                                    print(f"    [Slip] Confirmed clear with selector: {confirm_sel}")
                                    break
                            except:
                                continue

                        break
                except Exception as e:
                    print(f"    [Slip] Clear selector failed: {clear_sel} - {e}")
                    continue

            if bets_cleared:
                print("    [Slip] Successfully cleared all bets")
            else:
                print("    [Slip] Could not clear bets")

            # Close bet slip
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(1)
            except:
                pass

        else:
            print("    [Slip] Bet slip is already empty.")
    except Exception as e:
        print(f"    [Slip Warning] Failed to clear slip: {e}")
