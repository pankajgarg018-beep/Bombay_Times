from playwright.sync_api import Page


class BasePage:
    """BasePage: reusable methods for all pages.

    Provides navigation, clicking with fallbacks, explicit waits and simple assertions.
    """

    def __init__(self, page: Page, base_url: str = "https://www.bombaytimes.com"):
        self.page = page
        self.base_url = base_url.rstrip("/")

    def goto(self, path: str = ""):
        url = f"{self.base_url}{path}"
        self._ensure_page()
        self.page.goto(url)
        # Use 'load' to avoid indefinite waits when networkidle isn't reached
        try:
            self.page.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass

    def click(self, locator, timeout: int = 10000):
        """Click a locator with a visible check and explicit wait."""
        try:
            self._ensure_page()
            self.page.wait_for_selector(locator, timeout=timeout)
            self.page.locator(locator).click()
            return True
        except Exception:
            return False

    def click_role(self, role: str, name: str, timeout: int = 8000):
        """Try to click a control by ARIA role first (more robust for accessible sites)."""
        try:
            self._ensure_page()
            self.page.get_by_role(role, name=name).wait_for(state="visible", timeout=timeout)
            self.page.get_by_role(role, name=name).click()
            return True
        except Exception:
            return False

    def click_href_contains(self, href_segment: str, timeout: int = 8000):
        """Fallback: click an anchor whose href contains the provided segment."""
        locator = f'a[href*="{href_segment}"]'
        try:
            self._ensure_page()
            self.page.wait_for_selector(locator, timeout=timeout)
            self.page.locator(locator).first.click()
            return True
        except Exception:
            return False

    def _ensure_page(self):
        """Ensure `self.page` is open; if closed, try to recreate a page.

        Attempts to create a new Page from the existing context, and if that
        fails, creates a fresh context from the browser. This keeps session
        fixtures resilient when a page/context is closed by the application.
        """
        try:
            # if page exists and is open, nothing to do
            if self.page and not self.page.is_closed():
                return
        except Exception:
            # accessing is_closed may raise if page object is partially torn down
            pass

        # Try to create a new page from the old context
        try:
            ctx = getattr(self.page, "context", None)
            if ctx:
                new_page = ctx.new_page()
                self.page = new_page
                return
        except Exception:
            pass

        # Try to create a new context from the browser
        try:
            browser = getattr(getattr(self.page, "context", None), "browser", None)
            if browser:
                new_ctx = browser.new_context()
                new_page = new_ctx.new_page()
                self.page = new_page
                return
        except Exception:
            pass

        # If all attempts fail, raise to surface the underlying error
        raise RuntimeError("Unable to recreate Playwright Page; browser/context may be closed")

    def wait_for_url(self, expected: str, timeout: int = 10000):
        """Wait until the page URL matches the expected value (exact match).

        Use the full expected URL.
        """
        self.page.wait_for_url(expected, timeout=timeout)

    def click_and_wait_for_url(self, click_callable, expected_url: str, timeout: int = 10000):
        """Run click_callable (a lambda) then wait for expected_url."""
        click_callable()
        self.wait_for_url(expected_url, timeout=timeout)

    def get_text(self, locator: str, timeout: int = 8000) -> str:
        self.page.wait_for_selector(locator, timeout=timeout)
        return self.page.locator(locator).inner_text()
