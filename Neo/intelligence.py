"""
Intelligence Module - Unified AI Interface
Main entry point providing backwards compatibility with specialized AI components.
All advanced AI functionality is now handled by dedicated modules.
"""

import re
import asyncio
from typing import Optional

from playwright.async_api import Page

# Import specialized AI modules
from .selector_manager import SelectorManager
from .visual_analyzer import VisualAnalyzer
from .popup_handler import PopupHandler
from .page_analyzer import PageAnalyzer
from .utils import clean_json_response

# Legacy compatibility imports
from Helpers.Neo_Helpers.Managers.db_manager import knowledge_db
from Helpers.Neo_Helpers.Managers.api_key_manager import gemini_api_call_with_rotation


# Legacy compatibility functions - delegate to specialized modules
async def analyze_page_and_update_selectors(page, context_key: str, force_refresh: bool = False, info: Optional[str] = None):
    """Delegate to VisualAnalyzer"""
    return await VisualAnalyzer.analyze_page_and_update_selectors(page, context_key, force_refresh, info)


async def attempt_visual_recovery(page, context_name: str) -> bool:
    """Delegate to VisualAnalyzer"""
    return await VisualAnalyzer.attempt_visual_recovery(page, context_name)


def get_selector(context: str, element_key: str) -> str:
    """Delegate to SelectorManager"""
    return SelectorManager.get_selector(context, element_key)


async def get_selector_auto(page, context_key: str, element_key: str) -> str:
    """Delegate to SelectorManager"""
    return await SelectorManager.get_selector_auto(page, context_key, element_key)


async def extract_league_data(page, context_key: str = "home_page"):
    """Delegate to PageAnalyzer"""
    return await PageAnalyzer.extract_league_data(page, context_key)


async def fb_universal_popup_dismissal(page: Page, context: str = "fb_generic", html: Optional[str] = None, monitor_interval: int = 0) -> bool:
    """
    Universal pop-up dismissal. Handles close icons and multi-step tutorials.
    """
    for i in range(3): # Loop to handle multi-step dialogs or reappearing popups
        await asyncio.sleep(0.5) # Wait for animations
        found_and_clicked_popup = False

        try:
            # --- STRATEGY 1: Handle Guide/Tutorial Popups ("Next", "GOT IT!", etc.) ---
            guide_texts = ["GOT IT!", "Next", "Done", "Got it", "Skip"]
            for text in guide_texts:
                # Use a general button selector that contains the text
                try:
                    btn_locator = page.get_by_role("button", name=text, exact=False)
                    if await btn_locator.count() > 0:
                        btn = btn_locator.first
                        if await btn.is_visible(timeout=1000):
                            await btn.click(timeout=2000)
                            print(f"    [Popup Handler] Clicked guide button: '{text}'")
                            found_and_clicked_popup = True
                            break # Exit text loop and restart main loop
                except Exception:
                    continue # Try next text

            if found_and_clicked_popup:
                continue # Go to next iteration of the main loop

            # --- STRATEGY 2: Handle Popups with a standard close button (AI Selector) ---
            # Use non-healing get_selector to avoid expensive auto-heal on an optional element
            close_sel = get_selector(context, 'top_icon_close')
            if close_sel and await page.locator(close_sel).count() > 0:
                btn = page.locator(close_sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click(timeout=2000)
                    print(f"    [Popup Handler] Closed popup via AI selector.")
                    return True # This kind of popup is usually final

            # --- STRATEGY 3: Handle Popups with a standard close button (Fallback) ---
            fallback_selectors = [ 'svg.close-circle-icon', 'button[class*="close"]', '[data-testid*="close"]' ]
            for sel in fallback_selectors:
                 if await page.locator(sel).count() > 0:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click(timeout=2000)
                        print(f"    [Popup Handler] Closed popup via fallback selector: {sel}")
                        return True # This kind of popup is usually final

            # If we get here, no popups were handled
            print(f"    [Popup Handler] No dismissible popups found on attempt {i+1}.")
            return True

        except Exception as e:
            print(f"    [Popup Handler] Non-critical error on attempt {i+1}: {e}")
            pass

    print("    [Popup Handler] Finished checks, but popups might remain.")
    return True # Return true to not block the main script


async def fb_tooltip_btn(page: Page):
    """
    Closes feature tooltips, info dialogs, etc.
    Handles both "OK" buttons and "X" close icons robustly without hanging.
    """
    try:
        # Strategy 1: Look for an "OK" button in a dialog, as seen in new popup.html
        ok_button_selector = "div.dialog-container button:has-text('OK')"
        if await page.locator(ok_button_selector).count() > 0:
            btn = page.locator(ok_button_selector).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                print("    [Tooltip] Clicked OK button in dialog.")
                await asyncio.sleep(0.5)
                return

        # Strategy 2: Look for an AI-defined close icon (non-healing to prevent hangs)
        tooltip_sel = get_selector('fb_match_page', 'tooltip_icon_close')
        if tooltip_sel:
            if await page.locator(tooltip_sel).count() > 0:
                btn = page.locator(tooltip_sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    print(f"    [Tooltip] Closed via AI selector.")
                    await asyncio.sleep(0.5)
                    return
    except Exception as e:
        # Silent fail is acceptable here as tooltips are transient
        pass


# Module-level exports for backwards compatibility
__all__ = [
    'clean_json_response',
    'analyze_page_and_update_selectors',
    'attempt_visual_recovery',
    'get_selector',
    'get_selector_auto',
    'extract_league_data',
    'fb_universal_popup_dismissal',
    'fb_tooltip_btn',
    'SelectorManager',
    'VisualAnalyzer',
    'PopupHandler',
    'PageAnalyzer'
]
