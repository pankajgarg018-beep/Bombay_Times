"""Shared utility helpers for the BombayTimes test suite.

These functions are available for use in test files or page objects.
BasePage already provides similar functionality via its click() method,
but safe_click() can be used directly with a raw Playwright Page object
without instantiating a page object class.
"""

from playwright.sync_api import Page


def safe_click(page: Page, selector: str, timeout: int = 8000) -> bool:
    """Wait for *selector* to appear, then click it.

    Returns True on success, False if the element is not found or click fails.
    Useful for optional UI elements where a failure should not stop the test.
    """
    try:
        page.wait_for_selector(selector, timeout=timeout)
        page.locator(selector).click()
        return True
    except Exception:
        return False
