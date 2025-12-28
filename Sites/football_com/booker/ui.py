"""
Booker UI Utilities
Handles overlays, tutorials, and resilient click interactions.
"""

import asyncio
from playwright.async_api import Page, Locator
from Helpers.utils import log_error_state
from Neo.selector_manager import SelectorManager

async def handle_page_overlays(page: Page):
    """Forcefully hide or remove sticky elements that intercept clicks."""
    try:
        await page.keyboard.press("Escape")
    except: pass

    selectors = [
        "footer.CommentFooter", "section#event-detail-header-nav",
        "div.dialog-wrapper", ".m-dialog-mask", ".m-popup-mask",
        "div.srct-widget-indicator_custom", "div.m-main-right",
        "div.m-tutorial-mask", "div.m-tutorial"
    ]
    
    for selector in selectors:
        try:
            await page.evaluate(f"document.querySelectorAll('{selector}').forEach(el => el.style.display = 'none')")
        except: pass

async def robust_click(locator: Locator, page: Page, timeout: int = 5000):
    """A resilient click function that handles overlays and retries via dispatch_event."""
    try:
        await handle_page_overlays(page)
        if await locator.count() > 0:
            try:
                await locator.scroll_into_view_if_needed(timeout=2000)
            except: pass
            
            if await locator.is_visible(timeout=timeout):
                try:
                    await locator.click(timeout=timeout, force=True)
                    return True
                except Exception:
                    await locator.dispatch_event("click")
                    return True
        return False
    except Exception as e:
        print(f"    [Action Error] robust_click failed: {e}")
        return False

async def dismiss_overlays(page: Page):
    """Actively click 'Skip' or 'Close' on common UI overlays."""
    overlays = ["text='Next'", "text='Got it'", "text='Skip'", ".m-tutorial-close", ".m-close-btn"]
    for sel in overlays:
        try:
            if await page.locator(sel).first.is_visible(timeout=500):
                await page.locator(sel).first.click(timeout=1000)
        except: pass

async def wait_for_element(page: Page, selector: str, timeout: int = 10000) -> bool:
    """Helper to wait for visibility with boolean return."""
    try:
        await page.locator(selector).first.wait_for(state="visible", timeout=timeout)
        return True
    except: return False
