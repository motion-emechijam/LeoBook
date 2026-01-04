"""
Selector Manager Module
Handles CSS selector storage, retrieval, and management for web automation.
Responsible for maintaining the knowledge base of UI selectors with auto-healing capabilities.
"""

import os
from typing import Dict, Any, Optional

from Helpers.Neo_Helpers.Managers.db_manager import load_knowledge, save_knowledge, knowledge_db


class SelectorManager:
    """Manages CSS selectors for web automation with auto-healing capabilities"""

    @staticmethod
    def get_selector(context: str, element_key: str) -> str:
        """Legacy synchronous accessor (does not auto-heal)."""
        return knowledge_db.get(context, {}).get(element_key, "")

    @staticmethod
    async def get_selector_auto(page, context_key: str, element_key: str) -> str:
        """
        SMART ACCESSOR:
        1. Checks if selector exists in DB.
        2. Validates if selector is present on the current page.
        3. If missing or invalid, attempts AI re-analysis, but falls back gracefully.
        """
        # Import here to avoid circular imports
        from .intelligence import analyze_page_and_update_selectors

        # 1. Quick Lookup
        selector = knowledge_db.get(context_key, {}).get(element_key)

        # 2. Validation
        is_valid = False
        if selector:
            # --- NEW: Wait up to 2 minutes for the selector to be attached to the DOM ---
            # This prevents premature auto-healing due to network lag or slow rendering.
            try:
                # Use wait_for_selector which is more robust for this check.
                await page.wait_for_selector(selector, state='attached', timeout=5000)  # 5 seconds
                is_valid = True
            except Exception as e:
                print(f"    [Selector Stale] '{element_key}' ('{selector}') not found after 2 min wait.")
                is_valid = False

        # 3. Auto-Healing (with graceful fallback)
        if not is_valid:
            # --- NEW: Context Verification ---
            # Verify if we are actually on the page we think we are before healing.
            from .page_analyzer import PageAnalyzer
            content_is_correct = await PageAnalyzer.verify_page_context(page, context_key)
            
            if not content_is_correct:
                curr_url = page.url
                print(f"    [Auto-Heal Mismatch] Aborting repair for '{context_key}'. Page mismatch: {curr_url}")
                return str(selector or "")

            print(
                f"    [Auto-Heal] Selector '{element_key}' in '{context_key}' invalid/missing. Initiating AI repair..."
            )
            info = f"Selector '{element_key}' in '{context_key}' invalid/missing."
            try:
                # Run AI Analysis (which now captures its own snapshot)
                await analyze_page_and_update_selectors(page, context_key, force_refresh=True, info=info)

                # Re-fetch
                selector = knowledge_db.get(context_key, {}).get(element_key)

                if selector:
                    print(f"    [Auto-Heal Success] New selector for '{element_key}': {selector}")
                else:
                    print(f"    [Auto-Heal Failed] AI could not find '{element_key}' even after refresh.")
            except Exception as e:
                print(f"    [Auto-Heal Error] AI analysis failed for '{element_key}': {e}")
                selector = None

        # Return selector or empty string (callers should handle empty strings)
        result = selector or ""
        return str(result)

    @staticmethod
    def has_selectors_for_context(context: str) -> bool:
        """Check if selectors exist for a given context"""
        return context in knowledge_db and bool(knowledge_db[context])

    @staticmethod
    def get_all_selectors_for_context(context: str) -> Dict[str, str]:
        """Get all selectors for a specific context"""
        return knowledge_db.get(context, {})

    @staticmethod
    def update_selector(context: str, key: str, selector: str):
        """Update a specific selector in the knowledge base"""
        if context not in knowledge_db:
            knowledge_db[context] = {}
        knowledge_db[context][key] = selector
        save_knowledge()

    @staticmethod
    def remove_selector(context: str, key: str):
        """Remove a specific selector from the knowledge base"""
        if context in knowledge_db and key in knowledge_db[context]:
            del knowledge_db[context][key]
            save_knowledge()

    @staticmethod
    def clear_context_selectors(context: str):
        """Clear all selectors for a specific context"""
        if context in knowledge_db:
            knowledge_db[context] = {}
            save_knowledge()

    @staticmethod
    def get_contexts_list() -> list:
        """Get list of all available contexts"""
        return list(knowledge_db.keys())

    @staticmethod
    def validate_selector_format(selector: str) -> bool:
        """Basic validation of CSS selector format"""
        if not selector or not isinstance(selector, str):
            return False

        # Check for obviously invalid patterns
        invalid_patterns = [
            ':contains(',  # Non-standard jQuery selector
            'skeleton',    # Loading state selectors
            'ska__',       # Skeleton loading selectors
        ]

        for pattern in invalid_patterns:
            if pattern in selector.lower():
                return False

        return True

    # ===== POPUP-SPECIFIC SELECTOR MANAGEMENT =====

    @staticmethod
    def get_popup_selectors(context: str) -> list:
        """
        Get context-aware popup dismissal selectors with Phase 2 priority

        Args:
            context: Page context (fb_match_page, fb_general, generic)

        Returns:
            list: Ordered list of selectors (priority first)
        """
        # Phase 2: Football.com match page priority selectors - GUIDED TOUR SEQUENCE
        if context == 'fb_match_page':
            return [
                # Step 1: Next button for guided tour
                'button:has-text("Next")',
                'span:has-text("Next")',
                'button:has-text("Continue")',
                'span:has-text("Continue")',

                # Step 2: Got it completion buttons
                'button:has-text("Got it")',
                'button:has-text("Got it!")',
                'span:has-text("Got it")',
                'span:has-text("Got it!")',

                # Step 3: OK dismissal buttons (appears after tour)
                'button:has-text("OK")',
                'button:has-text("Ok")',
                'button:has-text("ok")',
                'span:has-text("OK")',
                'span:has-text("Ok")',
                'span:has-text("ok")',

                # Fallback close buttons
                'button:has-text("Skip")',
                'button:has-text("End Tour")',
                'button:has-text("Dismiss")',
                'button:has-text("Close")',
                'svg.close-circle-icon',
                'button.close',
                '[data-dismiss="modal"]',
                'svg[aria-label="Close"]',
                'button[aria-label="Close"]',
            ]

        # Football.com general pages
        elif context == 'fb_general':
            return [
                'button:has-text("Got it")',
                'button:has-text("OK")',
                'button:has-text("ok")',
                'button:has-text("Skip")',
                'button:has-text("End Tour")',
                'button:has-text("Dismiss")',
                'button:has-text("Close")',
                'svg.close-circle-icon',
                'button.close',
                '[data-dismiss="modal"]',
                'svg[aria-label="Close"]',
                'button[aria-label="Close"]',
                'button:has-text("Next")',
                'span:has-text("Next")',
            ]

        # Generic fallback selectors
        else:
            return [
                'button:has-text("Close")',
                'button:has-text("OK")',
                'button:has-text("Dismiss")',
                'button:has-text("Skip")',
                'button:has-text("Got it")',
                '[data-dismiss="modal"]',
                'svg[aria-label="Close"]',
                'button[aria-label="Close"]',
                'button.close',
                'svg.close-circle-icon',
                '.close',
                '[aria-label="Close"]',
            ]

    @staticmethod
    def learn_successful_selector(url: str, selector: str, context: Optional[str] = None):
        """
        Learn from successful popup dismissals and update knowledge base

        Args:
            url: Page URL where dismissal succeeded
            selector: Successful selector
            context: Page context (auto-detected if None)
        """
        if not context:
            context = SelectorManager._detect_context_from_url(url)

        # Update context-specific knowledge
        if context not in knowledge_db:
            knowledge_db[context] = {}

        # Store successful selector with timestamp
        import time
        knowledge_db[context][f'popup_close_{int(time.time())}'] = selector

        # Keep only recent successful selectors (last 50)
        popup_keys = [k for k in knowledge_db[context].keys() if k.startswith('popup_close_')]
        if len(popup_keys) > 50:
            # Remove oldest entries
            sorted_keys = sorted(popup_keys, key=lambda x: int(x.split('_')[-1]))
            for old_key in sorted_keys[:-50]:
                del knowledge_db[context][old_key]

        save_knowledge()
        print(f"[Selector Learning] Learned successful selector: {selector} for {context}")

    @staticmethod
    def get_learned_selectors(context: str) -> list:
        """
        Get selectors learned from successful dismissals

        Args:
            context: Page context

        Returns:
            list: Learned selectors ordered by recency
        """
        if context not in knowledge_db:
            return []

        popup_selectors = {}
        for key, selector in knowledge_db[context].items():
            if key.startswith('popup_close_'):
                timestamp = int(key.split('_')[-1])
                popup_selectors[timestamp] = selector

        # Return most recent selectors first
        return [popup_selectors[ts] for ts in sorted(popup_selectors.keys(), reverse=True)]

    @staticmethod
    def _detect_context_from_url(url: str) -> str:
        """Detect context from URL"""
        url_lower = url.lower()
        if 'football.com' in url_lower:
            if 'match' in url_lower or 'game' in url_lower:
                return 'fb_match_page'
            else:
                return 'fb_general'
        return 'generic'

    @staticmethod
    def get_all_popup_selectors(context: str) -> list:
        """
        Get complete list of popup selectors: learned + predefined

        Args:
            context: Page context

        Returns:
            list: Combined selectors with learned ones prioritized
        """
        learned = SelectorManager.get_learned_selectors(context)
        predefined = SelectorManager.get_popup_selectors(context)

        # Remove duplicates while preserving order (learned first)
        combined = learned + predefined
        seen = set()
        result = []
        for selector in combined:
            if selector not in seen:
                seen.add(selector)
                result.append(selector)

        return result
