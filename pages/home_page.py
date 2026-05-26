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
        """Open the site search bar efficiently.

        Uses instant count()-based presence checks (no timeout blocking) and
        short click timeouts so a missing element costs < 100 ms instead of
        the previous 8 000 – 10 000 ms per selector.
        """
        # Ordered by likelihood on bombaytimes.com — checked with count() (instant, no wait)
        trigger_selectors = [
            "div.search-feature > img[alt*='Search']",
            "img[alt='Search Icon']",
            "img[alt*='Search']",
            "button[aria-label*='search' i]",
            "button[class*='search' i]",
            "button:has(svg)",
            "header button:has(svg)",
            "nav button:has(svg)",
        ]

        # Selector that proves the input panel appeared
        _input_ready = (
            "input[name='search'], input[type='search'], "
            "input[aria-label*='search' i], input[name='q']"
        )

        for sel in trigger_selectors:
            try:
                loc = self.page.locator(sel).first
                if loc.count() == 0:
                    continue  # not in DOM — skip instantly (no timeout)
                loc.click(timeout=2000)  # short click timeout
                # Wait for the search input to become visible
                try:
                    self.page.wait_for_selector(_input_ready, state="visible", timeout=3000)
                except Exception:
                    pass
                return True
            except Exception:
                continue

        # Fallback: ARIA role with a very short timeout (avoids the old 8 s burn)
        try:
            self.page.get_by_role("button", name="Search").first.click(timeout=1500)
            return True
        except Exception:
            pass

        return False

    def perform_search(self, keyword: str):
        """Fill the search input and submit it with minimal delay.

        Key optimisations vs the old implementation:
        - Goes straight for ``input[name='search']`` (bombaytimes URL pattern confirms the name).
        - Uses ``fill()`` (instant) instead of ``keyboard.type()`` (character-by-character).
        - Presses Enter once — no JS event dispatch, no form-button hunting.
        - No network-response gate (10 000 ms) — the test's URL-wait handles results.
        """
        # Priority order — bombaytimes result URL is /searchresults?search=<kw>
        input_selectors = [
            "input[name='search']",        # ← bombaytimes-specific, confirmed by URL pattern
            "input[type='search']",
            "input[aria-label*='search' i]",
            "input[placeholder*='search' i]",
            "input[name='q']",
            "input[name='s']",
            ".search-box input",
            ".search-panel input",
            ".search-input input",
        ]

        found_sel = None
        for sel in input_selectors:
            try:
                loc = self.page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    found_sel = sel
                    break
            except Exception:
                continue

        if found_sel:
            try:
                inp = self.page.locator(found_sel).first
                inp.fill(keyword)          # instant — no per-character delay
                inp.press("Enter")         # submit
                return
            except Exception:
                pass

        # Fallback: type into whatever element currently has focus
        try:
            self.page.keyboard.type(keyword, delay=0)
            self.page.keyboard.press("Enter")
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
