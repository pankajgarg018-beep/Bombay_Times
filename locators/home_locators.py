"""CSS selector constants for the BombayTimes home page.

Usage: imported by HomePage (pages/home_page.py) as a reference.
The POM methods use inline role-based clicks with href fallbacks, so these
constants serve primarily as documentation and quick lookup references.
"""


class HomeLocators:
    # ── Header / Branding ─────────────────────────────────────────────────────
    LOGO = "a[href='/']"

    # ── Primary navigation ────────────────────────────────────────────────────
    ENTERTAINMENT     = "a[href*='/entertainment']"
    BOLLYWOOD         = "a[href*='/entertainment/bollywood']"
    LIFESTYLE         = "a[href*='/lifestyle']"
    PAWSOME           = "a[href*='/lifestyle/pawsome']"
    DINING            = "a[href*='/dining']"
    REVIEWS           = "a[href*='/dining/reviews']"
    TRAVEL            = "a[href*='/travel']"
    INDIA             = "a[href*='/travel/india']"
    PEOPLE            = "a[href*='/people']"
    INTERVIEWS        = "a[href*='/people/interviews']"
    SPECIALS          = "a[href*='/specials']"
    TAKE_TWO          = "a[href*='/specials/take-two']"
    ASTRO             = "a[href*='/astro']"
    TRENDS            = "a[href*='/astro/trends']"
    BT_PICKS          = "a[href*='/bt-picks']"
    ELECTRONICS       = "a[href*='/bt-picks/electronics']"
    INTIMATE_DIARIES  = "a[href*='/intimate-diaries']"

    # ── Overflow / hidden menu items ──────────────────────────────────────────
    FESTIVAL          = "a[href*='/festival']"
    PHOTO_STORIES     = "a[href*='/photo-stories']"
    VISUAL_STORIES    = "a[href*='/visual-stories']"
    LATEST_VIDEOS     = "a[href*='/latest-videos']"
    SHORT_VIDEOS      = "a[href*='/short-videos']"

    # ── Search ────────────────────────────────────────────────────────────────
    SEARCH_INPUT      = "input[type='search']"
    SEARCH_BUTTON     = "button[aria-label='Search']"
