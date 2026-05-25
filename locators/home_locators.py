"""Simple locator definitions for the Home page.

Note: many production sites change markup often. These locators use accessible
roles when possible, and fallback href-based selectors in the POM methods.
"""


class HomeLocators:
    # These are illustrative; the POM uses role-based clicks and href fallbacks.
    LOGO = "a[href='/']"
    ENTERTAINMENT = "a[href*='/entertainment']"
    BOLLYWOOD = "a[href*='/entertainment/bollywood']"
    LIFESTYLE = "a[href*='/lifestyle']"
    PAWSOME = "a[href*='/lifestyle/pawsome']"
    DINING = "a[href*='/dining']"
    REVIEWS = "a[href*='/dining/reviews']"
    TRAVEL = "a[href*='/travel']"
    INDIA = "a[href*='/travel/india']"
    PEOPLE = "a[href*='/people']"
    INTERVIEWS = "a[href*='/people/interviews']"
    SPECIALS = "a[href*='/specials']"
    INTERVIEWS = "a[href*='/specials/take-two']"
    ASTRO = "a[href*='/astro']"
    TRENDS = "a[href*='/astro/trends']"
    BT_PICKS = "a[href*='/bt-picks']"
    ELECTRONICS = "a[href*='/bt-picks/electronics']"
    INTIMATE_DIARIES = "a[href*='/intimate-diaries']"
    SEARCH_INPUT = "input[type='search']"
    SEARCH_BUTTON = "button[aria-label='Search']"
