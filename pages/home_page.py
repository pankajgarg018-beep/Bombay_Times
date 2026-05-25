from playwright.sync_api import Page, expect
from .base_page import BasePage
from locators.home_locators import HomeLocators


class HomePage(BasePage):
    """Page object for the Bombay Times home page and top navigation flows."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.loc = HomeLocators

    def go_home(self):
        self.goto("")

    # --- Entertainment flow ---
    def click_entertainment(self):
        # try accessible roles in order then href fallback
        if self.click_role("button", "Entertainment"):
            return
        if self.click_role("link", "Entertainment"):
            return
        if not self.click_href_contains("/entertainment"):
            self.goto("/entertainment")

    def click_bollywood(self):
        if self.click_role("button", "Bollywood"):
            return
        if self.click_role("link", "Bollywood"):
            return
        if not self.click_href_contains("/entertainment/bollywood"):
            self.goto("/entertainment/bollywood")

    # --- Lifestyle flow ---
    def click_lifestyle(self):
        if self.click_role("button", "Lifestyle"):
            return
        if self.click_role("link", "Lifestyle"):
            return
        if not self.click_href_contains("/lifestyle"):
            self.goto("/lifestyle")

    def click_pawsome(self):
        if self.click_role("button", "Pawsome"):
            return
        if self.click_role("link", "Pawsome"):
            return
        if not self.click_href_contains("/lifestyle/pawsome"):
            self.goto("/lifestyle/pawsome")

    # --- Dining flow ---
    def click_dining(self):
        if self.click_role("button", "Dining"):
            return
        if self.click_role("link", "Dining"):
            return
        if not self.click_href_contains("/dining"):
            self.goto("/dining")

    def click_reviews(self):
        if self.click_role("button", "Reviews"):
            return
        if self.click_role("link", "Reviews"):
            return
        if not self.click_href_contains("/dining/reviews"):
            self.goto("/dining/reviews")

    # --- Travel flow ---
    def click_travel(self):
        if self.click_role("button", "Travel"):
            return
        if self.click_role("link", "Travel"):
            return
        if not self.click_href_contains("/travel"):
            self.goto("/travel")

    def click_india(self):
        if self.click_role("button", "India"):
            return
        if self.click_role("link", "India"):
            return
        if not self.click_href_contains("/travel/india"):
            self.goto("/travel/india")

    # --- People / Interviews ---
    def click_people(self):
        if self.click_role("button", "People"):
            return
        if self.click_role("link", "People"):
            return
        if not self.click_href_contains("/people"):
            self.goto("/people")

    def click_interviews(self):
        if self.click_role("button", "Interviews"):
            return
        if self.click_role("link", "Interviews"):
            return
        if not self.click_href_contains("/people/interviews"):
            self.goto("/people/interviews")

    # --- Specials / Take Two ---
    def click_specials(self):
        if self.click_role("button", "Specials"):
            return
        if self.click_role("link", "Specials"):
            return
        if not self.click_href_contains("/specials"):
            self.goto("/specials")

    def click_take_two(self):
        if self.click_role("button", "Take Two"):
            return
        if self.click_role("link", "Take Two"):
            return
        if not self.click_href_contains("/specials/take-two"):
            self.goto("/specials/take-two")

    # --- Astro / Trends ---
    def click_astro(self):
        if self.click_role("button", "Astro"):
            return
        if self.click_role("link", "Astro"):
            return
        if not self.click_href_contains("/astro"):
            self.goto("/astro")

    def click_trends(self):
        if self.click_role("button", "Trends"):
            return
        if self.click_role("link", "Trends"):
            return
        if not self.click_href_contains("/astro/trends"):
            self.goto("/astro/trends")

    # --- BT Picks / Electronics ---
    def click_bt_picks(self):
        if self.click_role("button", "BT Picks"):
            return
        if self.click_role("link", "BT Picks"):
            return
        if not self.click_href_contains("/bt-picks"):
            self.goto("/bt-picks")

    def click_electronics(self):
        if self.click_role("button", "Electronics"):
            return
        if self.click_role("link", "Electronics"):
            return
        if not self.click_href_contains("/bt-picks/electronics"):
            self.goto("/bt-picks/electronics")

    # --- Intimate Diaries ---
    def click_intimate_diaries(self):
        if self.click_role("button", "Intimate Diaries"):
            return
        if self.click_role("link", "Intimate Diaries"):
            return
        if not self.click_href_contains("/intimate-diaries"):
            self.goto("/intimate-diaries")

    # --- Search flow ---
    def open_search(self):
        # Try role button first
        if self.click_role("button", "Search"):
            # wait for input to appear
            try:
                self.page.wait_for_selector("input[type='search'], input[aria-label*='search']", timeout=4000)
            except Exception:
                pass
            return

        # Fallback: try multiple attribute-based or xpath selectors
        selectors = [
            "button[aria-label*='search']",
            "button[title*='Search']",
            "button[class*='search']",
            "button[id*='search']",
            "a[href*='/search']",
            "button[type='submit']",
            "xpath=//button[contains(translate(@aria-label,'SEARCH','search'),'search')]",
            "xpath=//a[contains(translate(text(),'SEARCH','search'),'search')]",
            # target the visible search icon image specifically to avoid clicking other anchors
            "img[alt*='Search']",
            "div.search-feature > img[alt*='Search']",
            "xpath=//div[contains(@class,'search') or contains(@id,'search')]//button",
            # Try buttons that contain an SVG icon (common pattern for icon-only search buttons)
            "button:has(svg)",
            "header button:has(svg)",
            "nav button:has(svg)",
            "button[class*='icon']",
            "button[class*='toggle']",
            "button[class*='search-icon']",
        ]
        for sel in selectors:
            try:
                if self.click(sel):
                    try:
                        # Wait for either a search input or a search panel to appear
                        self.page.wait_for_selector(
                            "input[type='search'], input[aria-label*='search'], input[name='q'], .search-panel, .search-box, .search-input",
                            timeout=4000,
                        )
                    except Exception:
                        pass
                    return
            except Exception:
                continue

    def perform_search(self, keyword: str):
        # Attempt a few common search input approaches with explicit waits
        input_selectors = [
            "input[type='search']",
            "input[aria-label*='search']",
            "input[name='q']",
            "input[name='s']",
            "input#q",
        ]
        # Find the first visible input and use it
        visible_input = None
        for inp in input_selectors:
            try:
                loc = self.page.locator(inp).filter(has=self.page.locator(":visible"))
                if loc.count() > 0:
                    visible_input = inp
                    break
            except Exception:
                # fallback: try waiting for selector then assume it's visible
                try:
                    self.page.wait_for_selector(inp, timeout=1500)
                    visible_input = inp
                    break
                except Exception:
                    continue

        if visible_input:
            try:
                self.page.fill(visible_input, keyword)
            except Exception:
                try:
                    self.page.focus(visible_input)
                    self.page.keyboard.type(keyword)
                except Exception:
                    pass

            # Try to submit via nearby submit button or Enter
            try:
                # click submit inside same form if present
                try:
                    form = self.page.locator(f"{visible_input}").locator("..")
                    form.locator("button[type='submit']").click()
                except Exception:
                    pass
                try:
                    self.page.press(visible_input, "Enter")
                except Exception:
                    try:
                        self.page.keyboard.press("Enter")
                    except Exception:
                        pass
                # As a stronger fallback, dispatch keyboard events and submit via JS to trigger any client-side handlers
                try:
                    self.page.evaluate(
                        "(sel) => {\n                            const el = document.querySelector(sel) || document.querySelector('.search-box input') || document.querySelector('input.form-control') || document.querySelector('input[type=text]');\n                            if(!el) return false;\n                            el.focus();\n                            el.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, which:13, bubbles:true}));\n                            el.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', keyCode:13, which:13, bubbles:true}));\n                            el.dispatchEvent(new Event('change', {bubbles:true}));\n                            const form = el.closest('form');\n                            if(form) form.dispatchEvent(new Event('submit', {bubbles:true}));\n                            return true;\n                        }",
                        visible_input,
                    )
                except Exception:
                    pass
            except Exception:
                pass

            # Wait for either a network response related to search or common result containers
            try:
                # Wait for a network response that includes common search query params or path
                def is_search_response(resp):
                    try:
                        url = resp.url
                        lower = url.lower()
                        if "search" in lower or "q=" in lower or "?s=" in lower or "/search" in lower:
                            return True
                    except Exception:
                        return False
                    return False

                with self.page.expect_response(lambda r: is_search_response(r), timeout=10000) as resp_info:
                    # small pause to allow the request to start
                    self.page.wait_for_timeout(250)
                # if response is received, try to wait for result containers
                try:
                    result_css = [
                        "div.search-results",
                        "ul.search-list",
                        "div.search-list",
                        "article",
                        ".story-card",
                        ".listing",
                        ".search-results",
                    ]
                    joined = ",".join(result_css)
                    self.page.wait_for_selector(joined, timeout=5000)
                    return
                except Exception:
                    # if no selectors, still consider response as success
                    return
            except Exception:
                # network wait failed — try selector waits and URL-based detection as fallback
                try:
                    result_css = [
                        "div.search-results",
                        "ul.search-list",
                        "div.search-list",
                        "article",
                        ".story-card",
                        ".listing",
                        ".search-results",
                    ]
                    joined = ",".join(result_css)
                    self.page.wait_for_selector(joined, timeout=8000)
                    return
                except Exception:
                    try:
                        if "search" in self.page.url or "?s=" in self.page.url or "q=" in self.page.url:
                            return
                    except Exception:
                        pass

        # If we've reached here, search likely failed to produce results — capture artifacts
        try:
            import os, time

            artifacts_dir = os.path.join(os.getcwd(), ".test-artifacts")
            os.makedirs(artifacts_dir, exist_ok=True)
            ts = int(time.time())
            html_path = os.path.join(artifacts_dir, f"search_failure_{ts}.html")
            png_path = os.path.join(artifacts_dir, f"search_failure_{ts}.png")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.page.content())
            try:
                self.page.screenshot(path=png_path, full_page=True)
            except Exception:
                # ignore screenshot failures
                pass
        except Exception:
            pass

        # If no input found or no result detected, fall through to other strategies below

        # Last resort: try clicking the header search icon/area to reveal input, then type
        fallback_clickors = [
            "div.search-feature > img[alt*='Search']",
            "img[alt='Search Icon']",
            "img[alt*='Search']",
        ]
        for sel in fallback_clickors:
            try:
                if self.click(sel):
                    # wait for the input to appear after clicking the icon
                    try:
                        self.page.wait_for_selector(
                            "input[type='search'], input[aria-label*='search'], input[name='q'], .search-panel, .search-box, .search-input",
                            timeout=4000,
                        )
                        # fill the first visible input we can find
                        visible_input = None
                        for cand in ["input[type='search']", "input[aria-label*='search']", "input[name='q']", "input[name='s']", "input#q"]:
                            try:
                                locator = self.page.locator(cand).filter(has=self.page.locator(":visible"))
                                if locator.count() > 0:
                                    visible_input = cand
                                    break
                            except Exception:
                                continue
                        if visible_input:
                            self.page.fill(visible_input, keyword)
                        try:
                            # press Enter on the filled input if possible
                            if visible_input:
                                try:
                                    self.page.press(visible_input, "Enter")
                                except Exception:
                                    pass
                            else:
                                try:
                                    self.page.keyboard.press("Enter")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        return
                    except Exception:
                        # input didn't appear, continue trying other clickors
                        continue
            except Exception:
                continue

        # Final safeguard: ensure page still open then type into focused element
        try:
            if not self.page.is_closed():
                try:
                    self.page.keyboard.type(keyword)
                    self.page.keyboard.press("Enter")
                except Exception:
                    pass
        except Exception:
            pass

    def click_logo(self):
        # Try common logo patterns and fallbacks
        tried = self.click_role("link", "Bombay Times")
        if not tried:
            tried = self.click_href_contains("https://www.bombaytimes.com/")
        if not tried:
            # relative home link
            self.click_href_contains("/")

    def open_overflow_menu(self):
        """Open the three-dot / overflow menu contained in `div.b-none`."""
        selectors = [
            "div.b-none",
            "div.b-none button",
            "div.b-none .more",
            "button[aria-label*='more']",
            "button[aria-label*='menu']",
            "button[class*='more']",
        ]
        for sel in selectors:
            try:
                if self.click(sel):
                    # Wait for the Photo Stories link to become VISIBLE (not just attached)
                    try:
                        self.page.wait_for_selector(
                            "a:has-text('Photo Stories'), a[href*='photo-stories']",
                            state="visible",
                            timeout=8000,
                        )
                        return True
                    except Exception:
                        pass
                    # Item not visible — try next trigger selector
            except Exception:
                continue
        return False

    def click_photo_stories(self):
        # Direct visibility-checked click — most reliable when menu is already open
        for sel in [
            "a:has-text('Photo Stories')",
            "a[href*='/photo-stories']",
            "a[href*='photo-stories']",
        ]:
            try:
                loc = self.page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click()
                    return True
            except Exception:
                continue
        # Fallback to role/href helpers
        if self.click_role("link", "Photo Stories"):
            return True
        if self.click_href_contains("/photo-stories"):
            return True
        return False

    def click_web_stories(self):
        # Web Stories are under /visual-stories
        if self.click_role("link", "Web Stories"):
            return True
        if self.click_href_contains("/visual-stories"):
            return True
        try:
            if self.click("a:has-text('Web Stories')"):
                return True
        except Exception:
            pass
        return False

    def click_videos(self):
        # Latest Videos -> /latest-videos
        if self.click_role("link", "Videos"):
            return True
        if self.click_href_contains("/latest-videos"):
            return True
        try:
            if self.click("a:has-text('Videos')"):
                return True
        except Exception:
            pass
        return False

    def click_short_videos(self):
        # Short Videos -> /short-videos
        if self.click_role("link", "Short Videos"):
            return True
        if self.click_href_contains("/short-videos"):
            return True
        try:
            if self.click("a:has-text('Short Videos')"):
                return True
        except Exception:
            pass
        return False
