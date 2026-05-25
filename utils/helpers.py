from playwright.sync_api import Page


def safe_click(page: Page, selector: str, timeout: int = 8000) -> bool:
    """Try to wait for selector and click; return True on success."""
    try:
        page.wait_for_selector(selector, timeout=timeout)
        page.locator(selector).click()
        return True
    except Exception:
        return False
