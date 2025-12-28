"""
Navigator Module
Handles login, session management, balance extraction, and schedule navigation for Football.com.
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime as dt
from typing import Tuple, Optional, cast

from playwright.async_api import Browser, BrowserContext, Page

from Helpers.Site_Helpers.site_helpers import fb_universal_popup_dismissal
from Neo.intelligence import get_selector, fb_universal_popup_dismissal as neo_popup_dismissal
from Neo.selector_manager import SelectorManager
from Helpers.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT

PHONE = cast(str, os.getenv("FB_PHONE"))
PASSWORD = cast(str, os.getenv("FB_PASSWORD"))
AUTH_DIR = Path("DB/Auth")
AUTH_FILE = AUTH_DIR / "storage_state.json"

if not PHONE or not PASSWORD:
    raise ValueError("FB_PHONE and FB_PASSWORD environment variables must be set for login.")


async def load_or_create_session(browser: Browser) -> Tuple[BrowserContext, Page]:
    """Load saved session or create new one with login."""
    if AUTH_FILE.exists():
        print("  [Auth] Found saved session. Loading state...")
        try:
            context = await browser.new_context(
                storage_state=str(AUTH_FILE), 
                viewport={'width': 375, 'height': 812},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
            )
            page = await context.new_page()
            await page.goto("https://www.football.com/ng/", wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
 
            await asyncio.sleep(5)
            # Validate session by checking for login elements
            login_sel = get_selector("fb_login_page", "top_right_login")
            if login_sel and await page.locator(login_sel).count() > 0:
                print("  [Auth] Session expired. Performing new login...")
                await perform_login(page)
        except Exception as e:
            print(f"  [Auth] Failed to load session: {e}. Deleting corrupted file and logging in anew...")
            AUTH_FILE.unlink(missing_ok=True)
            context = await browser.new_context(
                viewport={'width': 375, 'height': 812},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
            )
            page = await context.new_page()
            await perform_login(page)
    else:
        print("  [Auth] No saved session found. Performing new login...")
        context = await browser.new_context(
            viewport={'width': 375, 'height': 812},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()
        await perform_login(page)

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(AUTH_FILE))
    #await neo_popup_dismissal(page, "fb_generic", monitor_interval=90)  # Advanced popup handling
    return context, page


async def perform_login(page: Page):
    print("  [Navigation] Going to Football.com...")
    await page.goto("https://www.football.com/ng/m/", wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
    await asyncio.sleep(15)
    #await fb_universal_popup_dismissal(page, context="fb_login_page")
    try:
        Login_selector = get_selector("fb_login_page", "top_right_login")
        if Login_selector and await page.locator(Login_selector).count() > 0:
             await page.click(Login_selector)
             print("  [Login] Login page clicked")
             await asyncio.sleep(5)
        
        mobile_selector = "input[type='tel'], input[placeholder*='Mobile']"
        password_selector = "input[type='password']"
        login_btn_selector = "button:has-text('Login')"

        # Fallbacks (Check existence before asking AI to save time)
        if not await page.locator(mobile_selector).count() > 0:
            mobile_selector = get_selector("fb_login_page", "center_input_mobile_number")
            # If DB selector is empty or invalid, use auto-healing
            if not mobile_selector or not await page.locator(mobile_selector).count() > 0:
                from Neo.intelligence import get_selector_auto
                mobile_selector = await get_selector_auto(page, "fb_login_page", "center_input_mobile_number")

        if not await page.locator(password_selector).count() > 0:
            password_selector = get_selector("fb_login_page", "center_input_password")
            # If DB selector is empty or invalid, use auto-healing
            if not password_selector or not await page.locator(password_selector).count() > 0:
                from Neo.intelligence import get_selector_auto
                password_selector = await get_selector_auto(page, "fb_login_page", "center_input_password")

        if not await page.locator(login_btn_selector).count() > 0:
            login_btn_selector = get_selector("fb_login_page", "bottom_button_login")
            # If DB selector is empty or invalid, use auto-healing
            if not login_btn_selector or not await page.locator(login_btn_selector).count() > 0:
                from Neo.intelligence import get_selector_auto
                login_btn_selector = await get_selector_auto(page, "fb_login_page", "bottom_button_login")

        # Ensure we have valid selectors before proceeding
        if not mobile_selector or not password_selector or not login_btn_selector:
            raise ValueError("Could not find valid selectors for login form elements")

        await page.wait_for_selector(mobile_selector, state="visible", timeout=15000)
        await page.fill(mobile_selector, PHONE)
        await asyncio.sleep(1)
        await page.fill(password_selector, PASSWORD)
        await asyncio.sleep(1)
        await page.click(login_btn_selector)
        print("  [Login] Login button clicked")
        await page.wait_for_load_state('networkidle', timeout=30000)
        await asyncio.sleep(5)
        print("[Login] Football.com Login Successful.")
    except Exception as e:
        print(f"[Login Error] {e}")
        raise


async def extract_balance(page: Page) -> float:
    """Extract account balance."""
    print("  [Money] Retrieving account balance...")
    try:
        balance_sel = get_selector("fb_main_page", "navbar_balance")
        
        if balance_sel and await page.locator(balance_sel).count() > 0:
            balance_text = await page.locator(balance_sel).inner_text(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
            import re
            cleaned_text = re.sub(r'[^\d.]', '', balance_text)
            if cleaned_text:
                #print(f"  [Money] Found balance: {balance_text}")
                return float(cleaned_text)
    except Exception as e:
        print(f"  [Money Error] Could not parse balance: {e}")
    return 0.0


async def navigate_to_schedule(page: Page):
    """Navigate to the full schedule page using robust hardcoded selectors."""

    # Priority-based selector fallback system (most specific to most general)
    selectors = [
        "a[href*='/ng/m/sport/football/schedule']",  # Exact Football.com schedule URL
        "a[href*='schedule']",                       # Any link containing "schedule"
        "text='Full Schedule'",                      # Text-based fallback
        "text='Schedule'",                          # Shorter text fallback
        "[data-op*='schedule']",                    # Data attribute fallback
    ]

    for selector in selectors:
        try:
            print(f"  [Navigation] Trying selector: {selector}")
            if await page.locator(selector).count() > 0:
                await page.locator(selector).first.click(timeout=5000)
                print("  [Navigation] Button clicked successfully.")
                await page.wait_for_load_state('domcontentloaded', timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                print("  [Navigation] Schedule page loaded.")
                return
            else:
                print(f"  [Navigation] Selector not found: {selector}")
        except Exception as e:
            print(f"  [Navigation] Selector failed: {selector} - {e}")
            continue

    # Final fallback: direct URL navigation
    print("  [Navigation] All selectors failed. Using direct URL navigation.")
    await page.goto("https://www.football.com/ng/m/sport/football/schedule", wait_until='domcontentloaded', timeout=30000)
    print("  [Navigation] Schedule page loaded via direct URL.")

async def select_target_date(page: Page, target_date: str) -> bool:
    """Select the target date in the schedule and validate using robust hardcoded selectors."""

    print(f"  [Navigation] Selecting date: {target_date}")

    # Priority-based selector system for date dropdown
    date_selectors = [
        "div.m-choose-time",           # Football.com time selector
        "[data-op*='time']",          # Data attribute fallback
        ".time-selector",             # Class-based fallback
        "select[name*='time']",       # Select element fallback
    ]

    # Find and click the date dropdown
    dropdown_found = False
    for selector in date_selectors:
        try:
            if await page.locator(selector).count() > 0:
                await page.locator(selector).first.click()
                print(f"  [Filter] Clicked date dropdown with selector: {selector}")
                dropdown_found = True
                await asyncio.sleep(1)
                break
        except Exception as e:
            print(f"  [Filter] Dropdown selector failed: {selector} - {e}")
            continue

    if not dropdown_found:
        print("  [Filter] Could not find date dropdown")
        return False

    # Parse target date and select appropriate day
    target_dt = dt.strptime(target_date, "%d.%m.%Y")
    if target_dt.date() == dt.now().date():
        possible_days = ["Today", "Today's"]
    else:
        full_day = target_dt.strftime("%A")
        short_day = target_dt.strftime("%a")
        possible_days = [full_day, short_day]

    print(f"  [Filter] Target day options: {possible_days}")

    # Try to find and click the target day
    day_found = False
    for day in possible_days:
        try:
            day_selector = f"text='{day}'"
            if await page.locator(day_selector).count() > 0:
                await page.locator(day_selector).first.click()
                print(f"  [Filter] Successfully selected: {day}")
                day_found = True
                break
        except Exception as e:
            print(f"  [Filter] Failed to select {day}: {e}")
            continue

    if not day_found:
        print(f"  [Filter] Day {possible_days} not available in dropdown for {target_date}")
        return False

    await page.wait_for_load_state('networkidle', timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
    await asyncio.sleep(2)

    # Sort by League (optional - may not always be available)
    try:
        league_sort_selectors = [
            "div.m-choose-sort",                    # Football.com sort dropdown
            "[data-op*='sort']",                   # Data attribute fallback
            "text='League'",                       # Direct text match
        ]

        for sort_sel in league_sort_selectors:
            try:
                if await page.locator(sort_sel).count() > 0:
                    await page.locator(sort_sel).first.click()
                    await asyncio.sleep(1)

                    # Try to select "League" from dropdown options
                    league_option = "text='League'"
                    if await page.locator(league_option).count() > 0:
                        await page.locator(league_option).first.click()
                        print("  [Filter] Successfully sorted by League")
                        await asyncio.sleep(2)
                    break
            except Exception as e:
                print(f"  [Filter] Sort selector failed: {sort_sel} - {e}")
                continue

    except Exception as e:
        print(f"  [Filter] League sorting failed (non-critical): {e}")

    # Basic validation - check if page loaded matches
    try:
        # Look for any match time elements to validate we're on the right date page
        time_selectors = [
            ".time",                              # Generic time class
            "[class*='time']",                    # Class containing 'time'
            "span:not(.divider)",                 # Football.com specific time format
        ]

        for time_sel in time_selectors:
            try:
                if await page.locator(time_sel).count() > 0:
                    sample_time = await page.locator(time_sel).first.inner_text(timeout=3000)
                    if sample_time and len(sample_time.strip()) > 0:
                        print(f"  [Navigation] Page validation successful - found match times")
                        return True
            except:
                continue

        print("  [Navigation] Page validation completed (no time elements found but proceeding)")
        return True

    except Exception as e:
        print(f"  [Navigation Error] Validation failed: {e}")
        return False
