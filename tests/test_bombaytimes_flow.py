import base64
import datetime
import logging
import pathlib
import re
import time

import pytest
from playwright.sync_api import expect
from pages.home_page import HomePage

logger = logging.getLogger(__name__)

# Keywords used to identify Google Analytics / GTM network calls
_GA_KEYWORDS = ["google-analytics", "googletagmanager", "gtag", "collect"]

# Shared state passed between tests without a new fixture
_shared: dict = {
    "bollywood_article_url": None,   # populated by test_bollywood_article_detail_flow
    "bollywood_amp_url":     None,   # amphtml href read directly from the article page
}


# ── Per-page canonical + GA validation helper ─────────────────────────────────

def _nav_and_validate(page, page_name, nav_fn, logger, store, log_timing=False):
    """
    Navigate to a page via *nav_fn*, then:
      1. Wait up to 15 s for load state.
      2. Hold for 5 s (visual confirmation, GA listener still active).
      3. Remove GA listener.
      4. Validate canonical URL matches opened page URL → PASS / FAIL.
      5. Validate ≥1 GA call fired → PASS / FAIL.
      6. Capture screenshot on any FAIL.
      7. Append result dict to *store*.

    Set *log_timing=True* to emit per-step execution timings (click, load,
    canonical, GA) — useful for diagnosing slow pages.

    Any exception raised by nav_fn is re-raised after recording the failure so
    the calling test still fails loudly.
    """
    ga_calls = []
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _tm: dict = {}   # timing checkpoints (only used when log_timing=True)

    def _on_response(resp):
        url = resp.url.lower()
        if any(kw in url for kw in _GA_KEYWORDS):
            ga_calls.append({"url": resp.url, "status": resp.status})

    # Attach listener BEFORE navigation so no GA calls are missed
    page.on("response", _on_response)

    opened_url = ""
    _nav_exc = None

    try:
        if log_timing:
            _tm["click_start"] = time.time()
        nav_fn()
        if log_timing:
            _tm["click_done"] = time.time()
            logger.info(
                "[%s] ⏱ Step 1 – Click/nav completed: %.2f s",
                page_name, _tm["click_done"] - _tm["click_start"],
            )
            _tm["load_start"] = time.time()
        try:
            page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass
        if log_timing:
            _tm["load_done"] = time.time()
            logger.info(
                "[%s] ⏱ Step 2 – Page load state reached: %.2f s",
                page_name, _tm["load_done"] - _tm["load_start"],
            )
        opened_url = page.url
        logger.info("[%s] Page loaded: %s", page_name, opened_url)
        logger.info("[%s] Holding for 5 s (visual confirmation)...", page_name)
        page.wait_for_timeout(5000)
    except Exception as exc:
        _nav_exc = exc
        logger.error("[%s] Navigation/load error: %s", page_name, exc)
        try:
            opened_url = page.url
        except Exception:
            pass
    finally:
        page.remove_listener("response", _on_response)

    # If navigation itself failed, record it and propagate
    if _nav_exc is not None:
        store.append({
            "page_name": page_name,
            "opened_url": opened_url,
            "canonical_href": "",
            "canonical_status": "FAIL",
            "canonical_error": f"Navigation error: {_nav_exc}",
            "ga_status": "FAIL",
            "ga_error": f"Navigation error: {_nav_exc}",
            "ga_calls_count": 0,
            "screenshot_b64": None,
            "timestamp": timestamp,
        })
        raise _nav_exc  # propagate so the test is marked FAILED

    # ── Canonical URL validation ──────────────────────────────────────────────
    if log_timing:
        _tm["can_start"] = time.time()
    canonical_href = ""
    canonical_status = "FAIL"
    canonical_error = ""
    try:
        canonical_link = page.locator("link[rel='canonical']")
        if canonical_link.count() > 0:
            canonical_href = canonical_link.first.get_attribute("href") or ""
            if canonical_href.rstrip("/") == opened_url.rstrip("/"):
                canonical_status = "PASS"
                logger.info("[%s] PASS Canonical: %s", page_name, canonical_href)
            else:
                canonical_status = "FAIL"
                canonical_error = f"Expected: {opened_url}  |  Got: {canonical_href}"
                logger.warning(
                    "[%s] FAIL Canonical: expected '%s' got '%s'",
                    page_name, opened_url, canonical_href,
                )
        else:
            canonical_status = "FAIL"
            canonical_error = "No <link rel='canonical'> found on page"
            logger.warning("[%s] FAIL Canonical: no canonical link on %s", page_name, opened_url)
    except Exception as exc:
        canonical_status = "FAIL"
        canonical_error = str(exc)
        logger.error("[%s] Canonical check exception: %s", page_name, exc)
    if log_timing:
        _tm["can_done"] = time.time()
        logger.info(
            "[%s] ⏱ Step 3 – Canonical validation: %.3f s | Result: %s",
            page_name, _tm["can_done"] - _tm["can_start"], canonical_status,
        )

    # ── GA calls validation ───────────────────────────────────────────────────
    if log_timing:
        _tm["ga_start"] = time.time()
    ga_status = "FAIL"
    ga_error = ""
    logger.info("[%s] GA calls captured: %d", page_name, len(ga_calls))
    if ga_calls:
        ga_status = "PASS"
        for c in ga_calls:
            logger.info("[%s]   GA [%d] %s", page_name, c["status"], c["url"])
        logger.info("[%s] PASS GA: %d call(s) fired", page_name, len(ga_calls))
    else:
        ga_error = "No GA calls captured during page load"
        logger.warning("[%s] FAIL GA: no GA calls captured", page_name)
    if log_timing:
        _tm["ga_done"] = time.time()
        logger.info(
            "[%s] ⏱ Step 4 – GA validation: %.3f s | Calls: %d | Result: %s",
            page_name, _tm["ga_done"] - _tm["ga_start"], len(ga_calls), ga_status,
        )
        _total = _tm["ga_done"] - _tm["click_start"]
        logger.info(
            "[%s] ⏱ TOTAL (excl. 5 s hold) — click: %.2f s | load: %.2f s | "
            "canonical: %.3f s | GA: %.3f s | TOTAL: %.2f s",
            page_name,
            _tm["click_done"] - _tm["click_start"],
            _tm["load_done"]  - _tm["load_start"],
            _tm["can_done"]   - _tm["can_start"],
            _tm["ga_done"]    - _tm["ga_start"],
            _total - 5.0,   # subtract the intentional 5 s visual hold
        )

    # ── Screenshot on any failure ─────────────────────────────────────────────
    screenshot_b64 = None
    if canonical_status == "FAIL" or ga_status == "FAIL":
        try:
            artifacts_dir = pathlib.Path(".test-artifacts")
            artifacts_dir.mkdir(exist_ok=True)
            ts = int(time.time())
            safe_name = (
                page_name.replace(" ", "_").replace(">", "")
                         .replace("/", "_").replace("\\", "_")
                         .replace(":", "").strip("_")
            )
            png_path = artifacts_dir / f"page_val_{safe_name}_{ts}.png"
            page.screenshot(path=str(png_path), full_page=True)
            screenshot_b64 = base64.b64encode(png_path.read_bytes()).decode()
            logger.info("[%s] Screenshot saved: %s", page_name, png_path.name)
        except Exception as exc:
            logger.warning("[%s] Screenshot capture failed: %s", page_name, exc)

    store.append({
        "page_name": page_name,
        "opened_url": opened_url,
        "canonical_href": canonical_href,
        "canonical_status": canonical_status,
        "canonical_error": canonical_error,
        "ga_status": ga_status,
        "ga_error": ga_error,
        "ga_calls_count": len(ga_calls),
        "screenshot_b64": screenshot_b64,
        "timestamp": timestamp,
    })


# ── Test cases ────────────────────────────────────────────────────────────────

@pytest.mark.order(1)
def test_entertainment_and_bollywood_flow(page, category_val_store):
    logger.info("=== START: test_entertainment_and_bollywood_flow ===")
    home = HomePage(page)

    logger.info("Navigating to homepage")
    home.go_home()
    logger.info("Homepage URL: %s", page.url)

    # Entertainment category
    logger.info("Navigating to Entertainment (canonical + GA validation)")
    _nav_and_validate(page, "Entertainment", home.click_entertainment, logger, category_val_store)
    logger.info("URL after Entertainment: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/entertainment"), \
        f"Expected entertainment URL, got: {page.url}"
    logger.info("PASS: Entertainment URL verified")

    # Bollywood subcategory
    logger.info("Navigating to Bollywood (canonical + GA validation)")
    _nav_and_validate(page, "Entertainment > Bollywood", home.click_bollywood, logger, category_val_store)
    logger.info("URL after Bollywood: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/entertainment/bollywood"), \
        f"Expected bollywood URL, got: {page.url}"
    logger.info("PASS: Bollywood URL verified")

    logger.info("=== END: test_entertainment_and_bollywood_flow ===")


def test_lifestyle_and_pawsome_flow(page, category_val_store):
    logger.info("=== START: test_lifestyle_and_pawsome_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    logger.info("Navigating to Lifestyle (canonical + GA validation)")
    _nav_and_validate(page, "Lifestyle", home.click_lifestyle, logger, category_val_store)
    logger.info("After Lifestyle: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/lifestyle")
    logger.info("PASS: Lifestyle URL verified")

    logger.info("Navigating to Pawsome (canonical + GA validation)")
    _nav_and_validate(page, "Lifestyle > Pawsome", home.click_pawsome, logger, category_val_store)
    logger.info("After Pawsome: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/lifestyle/pawsome")
    logger.info("PASS: Pawsome URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_lifestyle_and_pawsome_flow ===")


def test_dining_and_reviews_flow(page, category_val_store):
    logger.info("=== START: test_dining_and_reviews_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    logger.info("Navigating to Dining (canonical + GA validation)")
    _nav_and_validate(page, "Dining", home.click_dining, logger, category_val_store)
    logger.info("After Dining: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/dining")
    logger.info("PASS: Dining URL verified")

    logger.info("Navigating to Reviews (canonical + GA validation)")
    _nav_and_validate(page, "Dining > Reviews", home.click_reviews, logger, category_val_store)
    logger.info("After Reviews: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/dining/reviews")
    logger.info("PASS: Reviews URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_dining_and_reviews_flow ===")


def test_travel_and_india_flow(page, category_val_store):
    logger.info("=== START: test_travel_and_india_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    logger.info("Navigating to Travel (canonical + GA validation)")
    _nav_and_validate(page, "Travel", home.click_travel, logger, category_val_store)
    logger.info("After Travel: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/travel")
    logger.info("PASS: Travel URL verified")

    logger.info("Navigating to India (canonical + GA validation)")
    _nav_and_validate(page, "Travel > India", home.click_india, logger, category_val_store)
    logger.info("After India: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/travel/india")
    logger.info("PASS: India URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_travel_and_india_flow ===")


def test_people_and_interviews_flow(page, category_val_store):
    logger.info("=== START: test_people_and_interviews_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    logger.info("Navigating to People (canonical + GA validation)")
    _nav_and_validate(page, "People", home.click_people, logger, category_val_store)
    logger.info("After People: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/people")
    logger.info("PASS: People URL verified")

    logger.info("Navigating to Interviews (canonical + GA validation)")
    _nav_and_validate(page, "People > Interviews", home.click_interviews, logger, category_val_store)
    logger.info("After Interviews: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/people/interviews")
    logger.info("PASS: Interviews URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_people_and_interviews_flow ===")


def test_specials_and_take_two_flow(page, category_val_store):
    logger.info("=== START: test_specials_and_take_two_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    logger.info("Navigating to Specials (canonical + GA validation)")
    _nav_and_validate(page, "Specials", home.click_specials, logger, category_val_store)
    logger.info("After Specials: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/specials")
    logger.info("PASS: Specials URL verified")

    logger.info("Navigating to Take Two (canonical + GA validation)")
    _nav_and_validate(page, "Specials > Take Two", home.click_take_two, logger, category_val_store)
    logger.info("After Take Two: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/specials/take-two")
    logger.info("PASS: Take Two URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_specials_and_take_two_flow ===")


def test_astro_and_trends_flow(page, category_val_store):
    logger.info("=== START: test_astro_and_trends_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    logger.info("Navigating to Astro (canonical + GA validation)")
    _nav_and_validate(page, "Astro", home.click_astro, logger, category_val_store)
    logger.info("After Astro: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/astro")
    logger.info("PASS: Astro URL verified")

    logger.info("Navigating to Trends (canonical + GA validation)")
    _nav_and_validate(page, "Astro > Trends", home.click_trends, logger, category_val_store)
    logger.info("After Trends: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/astro/trends")
    logger.info("PASS: Trends URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_astro_and_trends_flow ===")


def test_bt_picks_and_electronics_flow(page, category_val_store):
    logger.info("=== START: test_bt_picks_and_electronics_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    logger.info("Navigating to BT Picks (canonical + GA validation)")
    _nav_and_validate(page, "BT Picks", home.click_bt_picks, logger, category_val_store)
    logger.info("After BT Picks: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/bt-picks")
    logger.info("PASS: BT Picks URL verified")

    logger.info("Navigating to Electronics (canonical + GA validation)")
    _nav_and_validate(page, "BT Picks > Electronics", home.click_electronics, logger, category_val_store)
    logger.info("After Electronics: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/bt-picks/electronics")
    logger.info("PASS: Electronics URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_bt_picks_and_electronics_flow ===")


def test_intimate_diaries_flow(page, category_val_store):
    logger.info("=== START: test_intimate_diaries_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    # ── Intimate Diaries — with per-step timing ───────────────────────────────
    logger.info("=== [Intimate Diaries] Performance timing enabled ===")
    logger.info("[Intimate Diaries] Navigating (canonical + GA validation + timing logs)")
    _nav_and_validate(
        page, "Intimate Diaries",
        home.click_intimate_diaries,
        logger, category_val_store,
        log_timing=True,        # ← emit click / load / canonical / GA timings
    )
    logger.info("After Intimate Diaries: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/intimate-diaries"), \
        f"Expected intimate-diaries URL, got: {page.url}"
    logger.info("PASS: Intimate Diaries URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")

    # ── Festival (overflow menu) — executes BEFORE Photo Stories ─────────────
    logger.info("Opening overflow menu for Festival")
    _t0 = time.time()
    opened = home.open_overflow_menu()
    logger.info("Overflow menu open attempt: %.2f s | opened: %s", time.time() - _t0, opened)
    assert opened, "Overflow menu did not open for Festival"
    logger.info("Navigating to Festival (canonical + GA validation)")
    _nav_and_validate(page, "Festival", home.click_festival, logger, category_val_store)
    logger.info("After Festival: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/festival"), \
        f"Unexpected URL after clicking Festival: {page.url}"
    logger.info("PASS: Festival URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage after Festival")

    # ── Photo Stories (overflow menu) ─────────────────────────────────────────
    logger.info("Opening overflow menu for Photo Stories")
    _t0 = time.time()
    opened = home.open_overflow_menu()
    logger.info("Overflow menu open attempt: %.2f s | opened: %s", time.time() - _t0, opened)
    assert opened, "Overflow menu did not open for Photo Stories"
    logger.info("Navigating to Photo Stories (canonical + GA validation)")
    _nav_and_validate(page, "Photo Stories", home.click_photo_stories, logger, category_val_store)
    logger.info("After Photo Stories: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/photo-stories"), \
        f"Unexpected URL after clicking Photo Stories: {page.url}"
    logger.info("PASS: Photo Stories URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")

    # ── Web Stories (overflow menu) ───────────────────────────────────────────
    logger.info("Opening overflow menu for Web Stories")
    _t0 = time.time()
    opened = home.open_overflow_menu()
    logger.info("Overflow menu open attempt: %.2f s | opened: %s", time.time() - _t0, opened)
    assert opened, "Overflow menu did not open for Web Stories"
    logger.info("Navigating to Web Stories (canonical + GA validation)")
    _nav_and_validate(page, "Web Stories", home.click_web_stories, logger, category_val_store)
    logger.info("After Web Stories: %s", page.url)
    expect(page).to_have_url("https://www.bombaytimes.com/visual-stories", timeout=10000)
    logger.info("PASS: Web Stories URL verified")

    home.click_logo()
    expect(page).to_have_url("https://www.bombaytimes.com/", timeout=10000)
    logger.info("PASS: Returned to homepage")

    # ── Latest Videos (overflow menu) ─────────────────────────────────────────
    logger.info("Opening overflow menu for Videos")
    _t0 = time.time()
    opened = home.open_overflow_menu()
    logger.info("Overflow menu open attempt: %.2f s | opened: %s", time.time() - _t0, opened)
    assert opened, "Overflow menu did not open for Videos"
    logger.info("Navigating to Latest Videos (canonical + GA validation)")
    _nav_and_validate(page, "Latest Videos", home.click_videos, logger, category_val_store)
    logger.info("After Videos: %s", page.url)
    expect(page).to_have_url("https://www.bombaytimes.com/latest-videos", timeout=10000)
    logger.info("PASS: Latest Videos URL verified")

    # ── Short Videos ──────────────────────────────────────────────────────────
    logger.info("Navigating to Short Videos (canonical + GA validation)")
    _nav_and_validate(page, "Short Videos", home.click_short_videos, logger, category_val_store)
    logger.info("After Short Videos: %s", page.url)
    expect(page).to_have_url("https://www.bombaytimes.com/short-videos", timeout=10000)
    logger.info("PASS: Short Videos URL verified")

    home.click_logo()
    expect(page).to_have_url("https://www.bombaytimes.com/", timeout=10000)
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_intimate_diaries_flow ===")


def test_bollywood_article_detail_flow(page, category_val_store):
    """
    Runs AFTER all category/subcategory pages.
    1. Navigate directly to Bollywood listing.
    2. Click the FIRST available article.
    3. Validate the detail page: 5 s hold + canonical + GA (recorded via _nav_and_validate).
    4. Also check Trending, Related, and amphtml presence.
    """
    logger.info("=== START: test_bollywood_article_detail_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    # Navigate directly to Bollywood listing
    logger.info("Navigating directly to Bollywood listing: /entertainment/bollywood")
    home.goto("/entertainment/bollywood")
    try:
        page.wait_for_load_state("load", timeout=15000)
    except Exception:
        pass
    logger.info("Bollywood listing URL: %s", page.url)

    # Wait for articles to render
    logger.info("Waiting for Bollywood article cards to render...")
    try:
        page.wait_for_selector("ol.sub-cat-ol li a, a.right-img-a", timeout=10000)
        logger.info("Article listing is ready")
    except Exception:
        logger.warning("Timed out waiting for listing — will attempt selectors anyway")

    _article_selectors = [
        "ol.sub-cat-ol li a.right-img-a",
        "ol.sub-cat-ol li a",
        "a.right-img-a",
        "a.newsItem[href*='/entertainment/bollywood']",
        "a.newsItem",
        "a[href*='/entertainment/bollywood/']",
        "figure a[href*='/entertainment']",
        "article a",
    ]

    def _click_bollywood_article():
        for sel in _article_selectors:
            try:
                loc = page.locator(sel).first
                count = loc.count()
                logger.debug("Article selector '%s' → %d element(s)", sel, count)
                if count > 0:
                    logger.info("Clicking first article using selector: %s", sel)
                    loc.click()
                    return
            except Exception as exc:
                logger.debug("Article selector '%s' raised: %s", sel, exc)
                continue
        logger.error("No article selector matched on Bollywood listing page")
        pytest.fail("Could not find any article to click on Bollywood listing page")

    try:
        logger.info("Navigating to Bollywood article detail (5 s hold + canonical + GA validation)")
        _nav_and_validate(
            page, "Bollywood Article (Detail)",
            _click_bollywood_article,
            logger, category_val_store,
        )
        article_url = page.url
        _shared["bollywood_article_url"] = article_url   # used by test_amp_page_validation
        # Also capture the amphtml URL directly from the page (more reliable than constructing it)
        _amp_link = page.locator("link[rel='amphtml']")
        if _amp_link.count() > 0:
            _shared["bollywood_amp_url"] = _amp_link.first.get_attribute("href") or ""
        logger.info("Bollywood article detail page: %s", article_url)

        # Trending section
        logger.info("Checking Trending section")
        has_trending = (
            page.locator(".trending, .trendingBlock, .trending-tag, [class*='trending']").count() > 0
            or page.get_by_text("Trending").count() > 0
        )
        if has_trending:
            logger.info("PASS: Trending section found")
        else:
            logger.warning("FAIL: Trending section NOT found on %s", article_url)
        assert has_trending, "Trending section not found on article page"

        # Related Articles section
        logger.info("Checking Related Articles section")
        has_related = (
            page.locator(".related, .related-articles, [class*='related']").count() > 0
            or page.get_by_text("Related Articles").count() > 0
            or page.get_by_text("Related").count() > 0
        )
        if has_related:
            logger.info("PASS: Related Articles section found")
        else:
            logger.warning("FAIL: Related Articles section NOT found on %s", article_url)
        assert has_related, "Related Articles section not found on article page"

        # Canonical URL (re-verify; _nav_and_validate already recorded status in store)
        logger.info("Re-verifying canonical URL on article page")
        canonical_link = page.locator("link[rel='canonical']")
        assert canonical_link.count() > 0, "Canonical link not found on article page"
        canonical_href = canonical_link.first.get_attribute("href")
        assert canonical_href, "Canonical href is empty"
        logger.info("Current URL:   %s", article_url)
        logger.info("Canonical URL: %s", canonical_href)
        assert canonical_href.rstrip("/") == article_url.rstrip("/"), \
            f"Canonical '{canonical_href}' does not match article URL '{article_url}'"
        logger.info("PASS: Canonical URL matches article URL")

        # amphtml
        logger.info("Checking amphtml link")
        amp = page.locator("link[rel='amphtml']")
        amp_count = amp.count()
        if amp_count > 0:
            logger.info("PASS: amphtml link found: %s", amp.first.get_attribute("href"))
        else:
            logger.warning("FAIL: amphtml link NOT found on %s", article_url)
        assert amp_count > 0, "amphtml link not present on article page"

    finally:
        logger.info("Navigating back to homepage (cleanup)")
        home.goto("")

    logger.info("URL after return: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_bollywood_article_detail_flow ===")


def test_amp_page_validation(page, amp_report_store):
    """
    Runs AFTER test_bollywood_article_detail_flow.
    Uses the same article URL; inserts amp/ before the numeric ID to form the
    AMP URL, then validates:
      A. Canonical — must point to the non-AMP article URL (no /amp/).
      B. AMP validation errors — captured via console listener + html[amp] check.
      C. Google Analytics — same GA keyword match used across the suite.
    All results written to amp_report_store for the dedicated HTML report section.
    No existing validations are changed.
    """
    logger.info("=== START: test_amp_page_validation ===")

    amp_report_store["run"] = True
    home = HomePage(page)

    # ── Step 1: Resolve the article URL (from shared state) ───────────────────
    article_url = _shared.get("bollywood_article_url")
    if not article_url:
        logger.warning("Bollywood article URL not set — navigating to listing for fallback")
        home.goto("/entertainment/bollywood")
        try:
            page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass
        _js_selectors_fallback = [
            "ol.sub-cat-ol li a.right-img-a",
            "ol.sub-cat-ol li a",
            "a.right-img-a",
            "a[href*='/entertainment/bollywood/']",
        ]
        for sel in _js_selectors_fallback:
            try:
                safe = sel.replace("'", "\\'")
                href = page.evaluate(f"() => {{ const el = document.querySelector('{safe}'); return el ? el.href : null; }}")
                if href and "bombaytimes.com" in href:
                    article_url = href
                    break
            except Exception:
                continue
    if not article_url:
        logger.error("Could not resolve article URL for AMP validation")
        amp_report_store["overall"] = "FAIL"
        pytest.fail("Could not resolve Bollywood article URL for AMP page validation")

    amp_report_store["article_url"] = article_url
    logger.info("Article URL: %s", article_url)

    # ── Step 2: Resolve AMP URL ───────────────────────────────────────────────
    # Priority: use the amphtml href captured directly from the article page.
    # Fallback: construct it by inserting amp/ before the trailing numeric ID.
    def _build_amp_url(url: str) -> str:
        u = url.rstrip("/")
        m = re.match(r'^(.*)/(\d{10,})$', u)   # numeric ID is typically 13 digits
        if m:
            return f"{m.group(1)}/amp/{m.group(2)}"
        parts = u.rsplit("/", 1)
        return f"{parts[0]}/amp/{parts[1]}" if len(parts) == 2 else u

    amp_url = _shared.get("bollywood_amp_url") or _build_amp_url(article_url)
    amp_report_store["amp_url"] = amp_url
    logger.info("AMP URL:     %s", amp_url)

    # ── Step 3: Navigate to AMP page — listen for GA + console in parallel ────
    ga_calls: list = []
    amp_console_errors: list = []

    def _on_response(resp):
        url = resp.url.lower()
        if any(kw in url for kw in _GA_KEYWORDS):
            ga_calls.append({"url": resp.url, "status": resp.status})

    def _on_console(msg):
        # AMP runtime logs validation errors as console errors/warnings
        if msg.type in ("error", "warning"):
            text = msg.text
            # Capture AMP-specific messages (validation errors, runtime errors)
            if any(kw in text.upper() for kw in ["AMP", "AMPHTML", "VALIDATION"]):
                amp_console_errors.append({"type": msg.type, "text": text})

    page.on("response", _on_response)
    page.on("console", _on_console)

    def _safe_goto_home():
        """Navigate to homepage robustly even if the current page is stuck."""
        try:
            # Stop any in-progress navigation before redirecting
            page.evaluate("() => { try { window.stop(); } catch(e) {} }")
        except Exception:
            pass
        for _wu in ("commit", "domcontentloaded", "load"):
            try:
                page.goto("https://www.bombaytimes.com", timeout=20000, wait_until=_wu)
                return
            except Exception:
                continue

    page_open_ok = False
    try:
        logger.info("Navigating to AMP page: %s", amp_url)
        # AMP pages can be slow — use domcontentloaded (faster than load) with 60 s
        page.goto(amp_url, timeout=60000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(3000)   # allow AMP runtime + analytics to initialise
        page_open_ok = True
        logger.info("AMP page opened: %s", page.url)
    except Exception as exc:
        logger.error("Failed to open AMP page: %s", exc)
        amp_report_store["page_open"] = False
        amp_report_store["overall"] = "FAIL"
    finally:
        page.remove_listener("response", _on_response)
        page.remove_listener("console", _on_console)

    amp_report_store["page_open"] = page_open_ok
    if not page_open_ok:
        logger.info("Navigating back to homepage (cleanup)")
        _safe_goto_home()
        return

    # ── Step A: AMP Canonical Validation ─────────────────────────────────────
    logger.info("--- AMP Canonical Validation ---")
    canonical_result = "FAIL"
    canonical_url   = ""
    canonical_error = ""
    try:
        can_loc = page.locator("link[rel='canonical']")
        if can_loc.count() > 0:
            canonical_url = can_loc.first.get_attribute("href") or ""
            amp_report_store["canonical_url"] = canonical_url
            if not canonical_url:
                canonical_error = "Canonical href attribute is empty"
                logger.warning("FAIL AMP Canonical: href is empty")
            elif "/amp/" in canonical_url:
                canonical_error = f"Canonical still contains /amp/: {canonical_url}"
                logger.warning("FAIL AMP Canonical: URL contains /amp/ — %s", canonical_url)
            elif canonical_url.rstrip("/") == article_url.rstrip("/"):
                canonical_result = "PASS"
                logger.info("PASS AMP Canonical: %s", canonical_url)
            else:
                canonical_error = (
                    f"Canonical '{canonical_url}' does not match article '{article_url}'"
                )
                logger.warning("FAIL AMP Canonical: mismatch — %s", canonical_error)
        else:
            canonical_error = "No link[rel='canonical'] found on AMP page"
            logger.warning("FAIL AMP Canonical: %s", canonical_error)
    except Exception as exc:
        canonical_error = str(exc)
        logger.error("AMP Canonical check raised: %s", exc)

    amp_report_store["canonical_result"] = canonical_result
    amp_report_store["canonical_error"]  = canonical_error

    # ── Step B: AMP Validation Error Check ───────────────────────────────────
    logger.info("--- AMP Validation Error Check ---")
    amp_error_status = "PASS"
    amp_errors_detail: list = []
    try:
        # Confirm this is actually an AMP page (html must have amp or ⚡ attribute)
        is_amp = page.evaluate("""
            () => {
                const html = document.documentElement;
                return html.hasAttribute('amp') || html.hasAttribute('⚡');
            }
        """)
        if not is_amp:
            amp_error_status = "FAIL"
            amp_errors_detail.append("Page does not have html[amp] or html[⚡] attribute — not a valid AMP page")
            logger.warning("FAIL AMP Validation: html[amp] attribute missing")
        else:
            logger.info("PASS: html[amp] attribute confirmed — valid AMP page")

        # Report any AMP console errors captured during navigation
        if amp_console_errors:
            amp_error_status = "FAIL"
            for e in amp_console_errors:
                msg = f"[{e['type'].upper()}] {e['text']}"
                amp_errors_detail.append(msg)
                logger.warning("AMP console %s: %s", e["type"], e["text"])
        else:
            logger.info("PASS: No AMP validation errors in console")

    except Exception as exc:
        amp_error_status = "FAIL"
        amp_errors_detail.append(f"AMP validation check raised: {exc}")
        logger.error("AMP validation check raised: %s", exc)

    amp_report_store["amp_error_status"]  = amp_error_status
    amp_report_store["amp_errors"]        = amp_errors_detail
    if amp_error_status == "PASS":
        logger.info("PASS AMP Validation: no errors detected")
    else:
        logger.warning("FAIL AMP Validation: %d issue(s) found", len(amp_errors_detail))

    # ── Step C: Google Analytics Validation ───────────────────────────────────
    logger.info("--- AMP GA Validation ---")
    ga_result = "FAIL"
    ga_error  = ""
    amp_report_store["ga_calls"] = ga_calls
    logger.info("GA calls captured on AMP page: %d", len(ga_calls))
    for e in ga_calls:
        logger.info("  GA [%d] %s", e["status"], e["url"])
    if ga_calls:
        bad = [e for e in ga_calls if e["status"] not in (200, 204)]
        if bad:
            ga_error = f"{len(bad)} GA call(s) returned error status"
            logger.warning("FAIL AMP GA: %s", ga_error)
        else:
            ga_result = "PASS"
            logger.info("PASS AMP GA: %d call(s) fired, all successful", len(ga_calls))
    else:
        ga_error = "No GA network calls captured on AMP page"
        logger.warning("FAIL AMP GA: %s", ga_error)

    amp_report_store["ga_result"] = ga_result
    amp_report_store["ga_error"]  = ga_error

    # ── Overall result ────────────────────────────────────────────────────────
    overall = "PASS" if all([
        canonical_result == "PASS",
        amp_error_status == "PASS",
        ga_result == "PASS",
    ]) else "FAIL"
    amp_report_store["overall"] = overall
    logger.info("AMP Page Validation Overall: %s", overall)
    logger.info(
        "  Canonical=%s | AMP Errors=%s | GA=%s",
        canonical_result, amp_error_status, ga_result,
    )

    logger.info("Navigating back to homepage (cleanup)")
    _safe_goto_home()
    logger.info("URL after return: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_amp_page_validation ===")


def test_photo_story_detail_flow(page, category_val_store):
    """
    1. Navigate directly to Photo Stories listing → 5 s hold + canonical + GA.
    2. Click the FIRST available photo story card.
    3. Validate the detail page: 5 s hold + canonical + GA (recorded via _nav_and_validate).
    """
    logger.info("=== START: test_photo_story_detail_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    # ── Step 1: Photo Stories listing page ───────────────────────────────────
    logger.info("Navigating to Photo Stories listing (5 s hold + canonical + GA validation)")
    _nav_and_validate(
        page,
        "Photo Stories Listing",
        lambda: home.goto("/photo-stories"),
        logger,
        category_val_store,
    )
    logger.info("Photo Stories listing URL: %s", page.url)
    assert "photo-stories" in page.url, \
        f"Expected photo-stories URL, got: {page.url}"
    logger.info("PASS: Photo Stories listing URL verified")

    # ── Step 2: Wait for listing articles to render ───────────────────────────
    logger.info("Waiting for photo story article cards to render...")
    try:
        page.wait_for_selector(
            "ol.sub-cat-ol li a, a.right-img-a, a[href*='/photo-stories/']",
            timeout=10000,
        )
        logger.info("Photo story cards are ready")
    except Exception:
        logger.warning("Timeout waiting for photo story cards — proceeding anyway")

    # ── Step 3: Build click function for first photo story card ───────────────
    _photo_selectors = [
        "ol.sub-cat-ol li a.right-img-a",
        "ol.sub-cat-ol li a",
        "a.right-img-a",
        "a[href*='/photo-stories/']",
        ".story-card a",
        ".photo-story a",
        "article a",
        "figure a",
        "a.newsItem",
    ]

    def _click_first_photo_story():
        for sel in _photo_selectors:
            try:
                loc = page.locator(sel).first
                count = loc.count()
                logger.debug("Photo selector '%s' → %d element(s)", sel, count)
                if count > 0:
                    logger.info("Clicking first photo story using selector: %s", sel)
                    loc.click()
                    return
            except Exception as exc:
                logger.debug("Photo selector '%s' raised: %s", sel, exc)
                continue
        logger.error("No photo story selector matched on listing page")
        pytest.fail("Could not find any photo story card to click on the listing page")

    # ── Step 4: Photo Story detail page → 5 s hold + canonical + GA ──────────
    try:
        logger.info("Clicking first photo story and validating detail page")
        _nav_and_validate(
            page,
            "Photo Story Detail",
            _click_first_photo_story,
            logger,
            category_val_store,
        )
        logger.info("Photo Story detail page validated: %s", page.url)
        logger.info("PASS: Photo Story detail flow complete")

    finally:
        logger.info("Navigating back to homepage (cleanup)")
        home.goto("")

    logger.info("URL after return: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_photo_story_detail_flow ===")


def test_visual_story_detail_flow(page, category_val_store):
    """
    Runs AFTER Photo Stories Detail.
    1. Navigate directly to Visual Stories listing: /visual-stories
    2. Click the FIRST visual story card.
    3. Validate the detail page: 5 s hold + canonical + GA (recorded via _nav_and_validate).
       Canonical URL MUST exactly match current page URL → FAIL if mismatch.
    """
    logger.info("=== START: test_visual_story_detail_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    # ── Step 1: Navigate to Visual Stories listing ─────────────────────────────
    logger.info("Navigating to Visual Stories listing: https://www.bombaytimes.com/visual-stories")
    home.goto("/visual-stories")
    try:
        page.wait_for_load_state("load", timeout=15000)
    except Exception:
        pass
    logger.info("Visual Stories listing URL: %s", page.url)
    assert "visual-stories" in page.url, \
        f"Expected visual-stories listing URL, got: {page.url}"
    logger.info("PASS: Visual Stories listing page opened")

    # ── Step 2: Wait for story cards to render ─────────────────────────────────
    logger.info("Waiting for Visual Story cards to render...")
    try:
        page.wait_for_selector(
            "ol.sub-cat-ol li a, a.right-img-a, "
            "a[href*='/visual-stories/'], .story-card a, article a, figure a",
            timeout=10000,
        )
        logger.info("Visual Story cards are ready")
    except Exception:
        logger.warning("Timeout waiting for visual story cards — proceeding anyway")

    # ── Step 3: Click function for first visual story ──────────────────────────
    _visual_selectors = [
        "ol.sub-cat-ol li a.right-img-a",
        "ol.sub-cat-ol li a",
        "a.right-img-a",
        "a[href*='/visual-stories/']",
        ".story-card a",
        ".visual-story a",
        "article a",
        "figure a",
        "a.newsItem",
    ]

    def _click_first_visual_story():
        for sel in _visual_selectors:
            try:
                loc = page.locator(sel).first
                count = loc.count()
                logger.debug("Visual selector '%s' → %d element(s)", sel, count)
                if count > 0:
                    logger.info("Clicking first visual story using selector: %s", sel)
                    loc.click()
                    return
            except Exception as exc:
                logger.debug("Visual selector '%s' raised: %s", sel, exc)
                continue
        logger.error("No visual story selector matched on listing page")
        pytest.fail("Could not find any visual story card to click on the listing page")

    # ── Step 4: Detail page — 5 s hold + canonical + GA ───────────────────────
    try:
        logger.info("Clicking first visual story and validating detail page")
        _nav_and_validate(
            page,
            "Visual Story Detail",
            _click_first_visual_story,
            logger,
            category_val_store,
        )
        logger.info("Visual Story detail page URL: %s", page.url)
        logger.info("PASS: Visual Story detail page — canonical & GA validated")

    finally:
        logger.info("Navigating back to homepage (cleanup)")
        home.goto("")

    logger.info("URL after return: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_visual_story_detail_flow ===")


def test_latest_video_detail_flow(page, category_val_store):
    """
    Runs AFTER Visual Story Detail.
    1. Navigate directly to Latest Videos listing: /latest-videos
    2. Click the FIRST video card.
    3. Validate the detail page: 5 s hold + canonical + GA (recorded via _nav_and_validate).
       Canonical URL MUST exactly match current page URL → FAIL if mismatch.
    """
    logger.info("=== START: test_latest_video_detail_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    # ── Step 1: Navigate to Latest Videos listing ──────────────────────────────
    logger.info("Navigating to Latest Videos listing: https://www.bombaytimes.com/latest-videos")
    home.goto("/latest-videos")
    try:
        page.wait_for_load_state("load", timeout=15000)
    except Exception:
        pass
    logger.info("Latest Videos listing URL: %s", page.url)
    assert "latest-videos" in page.url, \
        f"Expected latest-videos listing URL, got: {page.url}"
    logger.info("PASS: Latest Videos listing page opened")

    # ── Step 2: Allow JavaScript components to fully render ────────────────────
    # /latest-videos uses hidden carousels (href-style class); networkidle + a
    # brief extra pause ensures all deferred scripts have run.
    logger.info("Waiting for /latest-videos JavaScript components to render...")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(2000)   # brief extra settle for carousel init

    # ── Step 3: Extract first video URL via JavaScript (bypasses visibility) ───
    # The video items live in a hidden container; Playwright's visibility checks
    # reject them. We use JavaScript querySelector to find the href directly,
    # then navigate to it — functionally identical to clicking the card.
    _js_selectors = [
        "a.href-style[href*='/short-videos/']",       # confirmed by DOM inspection
        "a.videoplay-icon[href*='/short-videos/']",   # companion play-icon link
        "a[href*='/short-videos/']",                  # any short-video link
        "a.href-style",                               # any href-style link
        "a.newsItem[href*='/entertainment/']",        # sidebar article fallback
        "a.newsItem",                                 # last-resort any newsItem
    ]

    def _click_first_video():
        """Extract the first video URL via JS then navigate to it directly."""
        for sel in _js_selectors:
            try:
                # Escape selector for JS string (CSS attr-selector uses quotes)
                safe_sel = sel.replace("'", "\\'")
                href = page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('{safe_sel}');
                        return (el && el.href) ? el.href : null;
                    }}
                """)
                if href and "bombaytimes.com" in href and href != page.url:
                    logger.info("JS-extracted video URL via selector '%s': %s", sel, href)
                    page.goto(href)   # direct navigation — triggers GA, no visibility gate
                    return
                if href:
                    logger.debug("JS selector '%s' → href ignored (same page or off-domain): %s", sel, href)
            except Exception as exc:
                logger.debug("JS selector '%s' raised: %s", sel, exc)
        logger.error("No video link found on listing page via JavaScript extraction")
        pytest.fail("Could not find any video link on the /latest-videos listing page")

    # ── Step 4: Detail page — 5 s hold + canonical + GA ───────────────────────
    try:
        logger.info("Clicking first video and validating detail page")
        _nav_and_validate(
            page,
            "Latest Video Detail",
            _click_first_video,
            logger,
            category_val_store,
        )
        logger.info("Latest Video detail page URL: %s", page.url)
        logger.info("PASS: Latest Video detail page — canonical & GA validated")

    finally:
        logger.info("Navigating back to homepage (cleanup)")
        home.goto("")

    logger.info("URL after return: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_latest_video_detail_flow ===")


def test_bt_picks_detail_flow(page, category_val_store):
    """
    Runs AFTER Latest Video Detail.
    1. Navigate to BT Picks Electronics listing: /bt-picks/electronics
    2. Scroll to 'Top Pick From The Editors This Week' section and click first article.
    3. Validate the detail page: 5 s hold + canonical + GA (recorded via _nav_and_validate).
       Canonical URL MUST exactly match current page URL.
    """
    logger.info("=== START: test_bt_picks_detail_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    # ── Step 1: Navigate to BT Picks Electronics listing ──────────────────────
    logger.info("Navigating to BT Picks Electronics: https://www.bombaytimes.com/bt-picks/electronics")
    home.goto("/bt-picks/electronics")
    try:
        page.wait_for_load_state("load", timeout=15000)
    except Exception:
        pass
    logger.info("BT Picks Electronics listing URL: %s", page.url)
    assert "bt-picks/electronics" in page.url, \
        f"Expected bt-picks/electronics listing URL, got: {page.url}"
    logger.info("PASS: BT Picks Electronics listing page opened")

    # ── Step 2: Allow JavaScript components to fully render ────────────────────
    logger.info("Waiting for BT Picks Electronics JavaScript components to render...")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    # ── Step 3: Extract first article URL via JavaScript ───────────────────────
    # Diagnostic confirmed: H1.category-pagetitle = "Top Pick From The Editors This Week"
    # and a[href*='/bt-picks/electronics/'] returns 3 items on the listing page.
    _bt_js_selectors = [
        "a[href*='/bt-picks/electronics/']",   # confirmed by DOM inspection
        "a.newsItem[href*='/bt-picks/']",
        "a[href*='/bt-picks/']",
        "a.href-style[href*='/bt-picks/']",
        "a.right-img-a",
    ]

    def _click_first_bt_picks():
        """Scroll to Top-Pick section then extract first article URL via JS."""
        # Scroll to the 'Top Pick From' heading so it's in viewport
        try:
            page.evaluate("""
                () => {
                    const allEls = [...document.querySelectorAll('*')];
                    const heading = allEls.find(el =>
                        el.innerText && el.innerText.trim().includes('Top Pick From')
                        && el.children.length < 5
                    );
                    if (heading) {
                        heading.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }
            """)
            page.wait_for_timeout(800)
        except Exception:
            pass

        # Extract the first article link via JS
        for sel in _bt_js_selectors:
            try:
                safe_sel = sel.replace("'", "\\'")
                href = page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('{safe_sel}');
                        return (el && el.href) ? el.href : null;
                    }}
                """)
                if href and "bombaytimes.com" in href and href != page.url:
                    logger.info("JS-extracted BT Picks URL via selector '%s': %s", sel, href)
                    page.goto(href)
                    return
                if href:
                    logger.debug("JS selector '%s' - href ignored (same page or off-domain): %s", sel, href)
            except Exception as exc:
                logger.debug("JS selector '%s' raised: %s", sel, exc)
        logger.error("No BT Picks article link found via JavaScript extraction")
        pytest.fail("Could not find any BT Picks article link on the /bt-picks/electronics listing page")

    # ── Step 4: Detail page — 5 s hold + canonical + GA ───────────────────────
    try:
        logger.info("Clicking first BT Picks article and validating detail page")
        _nav_and_validate(
            page,
            "BT Picks Detail",
            _click_first_bt_picks,
            logger,
            category_val_store,
        )
        logger.info("BT Picks detail page URL: %s", page.url)
        logger.info("PASS: BT Picks detail page - canonical & GA validated")

    finally:
        logger.info("Navigating back to homepage (cleanup)")
        home.goto("")

    logger.info("URL after return: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_bt_picks_detail_flow ===")


def test_intimate_diaries_detail_flow(page, category_val_store):
    """
    Runs AFTER BT Picks Detail.
    1. Navigate to Intimate Diaries listing: /intimate-diaries
    2. Locate first article near the 'Tanisha Rao' author section and click it.
    3. Validate the detail page: 5 s hold + canonical + GA (recorded via _nav_and_validate).
       Canonical URL MUST exactly match current page URL.
    """
    logger.info("=== START: test_intimate_diaries_detail_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    # ── Step 1: Navigate to Intimate Diaries listing ───────────────────────────
    logger.info("Navigating to Intimate Diaries: https://www.bombaytimes.com/intimate-diaries")
    home.goto("/intimate-diaries")
    try:
        page.wait_for_load_state("load", timeout=15000)
    except Exception:
        pass
    logger.info("Intimate Diaries listing URL: %s", page.url)
    assert "intimate-diaries" in page.url, \
        f"Expected intimate-diaries listing URL, got: {page.url}"
    logger.info("PASS: Intimate Diaries listing page opened")

    # ── Step 2: Allow JavaScript components to fully render ────────────────────
    logger.info("Waiting for Intimate Diaries JavaScript components to render...")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    # ── Step 3: Extract first article URL via JavaScript ───────────────────────
    # Diagnostic confirmed: H2 = "Tanisha Rao" is present, and
    # a[href*='/intimate-diaries/'] returns 31 links on the listing page.
    def _click_first_intimate_diaries():
        """Find article near Tanisha Rao section then navigate to it via JS."""
        href = page.evaluate("""
            () => {
                // Strategy 1: Find Tanisha Rao heading and traverse up for article links
                const allEls = [...document.querySelectorAll(
                    'h1,h2,h3,h4,h5,h6,strong,span,div,p'
                )];
                const authorEl = allEls.find(el =>
                    el.innerText && el.innerText.trim() === 'Tanisha Rao'
                    && el.children.length < 3
                );
                if (authorEl) {
                    let container = authorEl;
                    for (let i = 0; i < 8; i++) {
                        const links = [...container.querySelectorAll(
                            'a[href*="/intimate-diaries/"]'
                        )].filter(a => a.href && !a.href.endsWith('/intimate-diaries/'));
                        if (links.length > 0) {
                            return links[0].href;
                        }
                        container = container.parentElement;
                        if (!container) break;
                    }
                }
                // Strategy 2: First intimate-diaries article link on page (fallback)
                const links = [...document.querySelectorAll(
                    'a[href*="/intimate-diaries/"]'
                )].filter(a => a.href && !a.href.endsWith('/intimate-diaries/'));
                return links.length > 0 ? links[0].href : null;
            }
        """)
        if href and "bombaytimes.com" in href and href != page.url:
            logger.info("JS-extracted Intimate Diaries URL: %s", href)
            page.goto(href)
            return
        if href:
            logger.debug("JS extraction returned href but same page or off-domain: %s", href)
        logger.error("No Intimate Diaries article link found via JavaScript extraction")
        pytest.fail("Could not find any Intimate Diaries article link on the listing page")

    # ── Step 4: Detail page — 5 s hold + canonical + GA ───────────────────────
    try:
        logger.info("Clicking first Intimate Diaries article and validating detail page")
        _nav_and_validate(
            page,
            "Intimate Diaries Detail",
            _click_first_intimate_diaries,
            logger,
            category_val_store,
        )
        logger.info("Intimate Diaries detail page URL: %s", page.url)
        logger.info("PASS: Intimate Diaries detail page - canonical & GA validated")

    finally:
        logger.info("Navigating back to homepage (cleanup)")
        home.goto("")

    logger.info("URL after return: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_intimate_diaries_detail_flow ===")


def test_astro_trends_detail_flow(page, category_val_store):
    """
    Runs AFTER Intimate Diaries Detail.
    1. Navigate to Astro Trends subcategory listing: /astro/trends
    2. Click the first article available on the listing page.
    3. Validate the detail page: 5 s hold + canonical + GA (recorded via _nav_and_validate).
       Canonical URL MUST exactly match current page URL.
    """
    logger.info("=== START: test_astro_trends_detail_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    # ── Step 1: Navigate to Astro Trends subcategory listing ──────────────────
    logger.info("Navigating to Astro Trends: https://www.bombaytimes.com/astro/trends")
    home.goto("/astro/trends")
    try:
        page.wait_for_load_state("load", timeout=15000)
    except Exception:
        pass
    logger.info("Astro Trends listing URL: %s", page.url)
    assert "astro/trends" in page.url, \
        f"Expected astro/trends listing URL, got: {page.url}"
    logger.info("PASS: Astro Trends listing page opened")

    # ── Step 2: Allow JavaScript components to fully render ────────────────────
    logger.info("Waiting for Astro Trends JavaScript components to render...")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    # ── Step 3: Extract first article URL via JavaScript ───────────────────────
    # Try ordered selectors — JS extraction bypasses visibility gates on deferred
    # content and is consistent with the pattern used in the other detail flows.
    _astro_js_selectors = [
        "ol.sub-cat-ol li a.right-img-a",        # image link in subcategory list
        "ol.sub-cat-ol li a",                     # any link in subcategory list
        "a.right-img-a[href*='/astro/']",         # right-image anchor for astro
        "a.newsItem[href*='/astro/']",            # generic news item for astro
        "a[href*='/astro/trends/']",              # any trends article link
        "a[href*='/astro/']",                     # any astro article link
    ]

    def _click_first_astro():
        """Extract the first Astro Trends article URL via JS then navigate to it."""
        for sel in _astro_js_selectors:
            try:
                safe_sel = sel.replace("'", "\\'")
                href = page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('{safe_sel}');
                        return (el && el.href) ? el.href : null;
                    }}
                """)
                if href and "bombaytimes.com" in href and href != page.url:
                    logger.info("JS-extracted Astro Trends URL via selector '%s': %s", sel, href)
                    page.goto(href)
                    return
                if href:
                    logger.debug("JS selector '%s' - href ignored (same page or off-domain): %s", sel, href)
            except Exception as exc:
                logger.debug("JS selector '%s' raised: %s", sel, exc)
        logger.error("No Astro Trends article link found via JavaScript extraction")
        pytest.fail("Could not find any article link on the /astro/trends listing page")

    # ── Step 4: Detail page — 5 s hold + canonical + GA ───────────────────────
    try:
        logger.info("Clicking first Astro Trends article and validating detail page")
        _nav_and_validate(
            page,
            "Astro Trends Detail",
            _click_first_astro,
            logger,
            category_val_store,
        )
        logger.info("Astro Trends detail page URL: %s", page.url)
        logger.info("PASS: Astro Trends detail page - canonical & GA validated")

    finally:
        logger.info("Navigating back to homepage (cleanup)")
        home.goto("")

    logger.info("URL after return: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_astro_trends_detail_flow ===")


def test_google_analytics_tracking(page, ga_report_store):
    logger.info("=== START: test_google_analytics_tracking ===")

    ga_keywords = ["google-analytics", "googletagmanager", "gtag", "collect"]
    ga_responses = []

    def handle_response(response):
        url = response.url.lower()
        if any(kw in url for kw in ga_keywords):
            ga_responses.append({"url": response.url, "status": response.status})
            logger.info("GA network call captured: [%d] %s", response.status, response.url)

    # Attach listener BEFORE navigation so no requests are missed
    page.on("response", handle_response)
    try:
        logger.info("Navigating to homepage: https://www.bombaytimes.com")
        page.goto("https://www.bombaytimes.com")
        # networkidle ensures analytics beacons (fetch/XHR) have had time to fire
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
            logger.info("Page reached networkidle state")
        except Exception:
            logger.warning("networkidle timed out — proceeding with captured calls so far")
        logger.info("Page URL: %s", page.url)
    finally:
        page.remove_listener("response", handle_response)

    # Log full summary
    logger.info("── GA network calls summary ──────────────────────────")
    logger.info("Total GA-related calls captured: %d", len(ga_responses))
    for entry in ga_responses:
        logger.info("  [%d] %s", entry["status"], entry["url"])
    logger.info("──────────────────────────────────────────────────────")

    # Populate the report store so the custom HTML report can render the GA section
    failed_calls = [e for e in ga_responses if e["status"] not in (200, 204)]
    ga_report_store["calls"] = list(ga_responses)
    ga_report_store["total"] = len(ga_responses)
    ga_report_store["failed_calls"] = failed_calls
    ga_report_store["passed"] = len(ga_responses) > 0 and not failed_calls

    # Assertion 1: at least one GA call must be present
    assert len(ga_responses) > 0, (
        "No Google Analytics tracking calls found on homepage. "
        "Expected URLs containing: google-analytics, googletagmanager, gtag, or collect"
    )
    logger.info("PASS: %d GA call(s) found on homepage", len(ga_responses))

    # Assertion 2: every GA call must return HTTP 200 or 204
    for e in failed_calls:
        logger.error("FAIL: GA call returned unexpected status %d: %s", e["status"], e["url"])
    assert not failed_calls, (
        f"{len(failed_calls)} GA call(s) returned non-200/204 status: "
        + ", ".join(f"[{e['status']}] {e['url']}" for e in failed_calls)
    )
    logger.info("PASS: All %d GA call(s) returned successful status (200 or 204)", len(ga_responses))
    logger.info("=== END: test_google_analytics_tracking ===")


def test_search_flow(page):
    """Optimised search test with per-step timing logs.

    Step 1 — Open search bar       → measured with time.time()
    Step 2 — Type keyword          → measured with time.time()
    Step 3 — Wait for results page → URL-pattern wait (no selector loops)
    """
    logger.info("=== START: test_search_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    # ── Step 1: Open the search bar ───────────────────────────────────────────
    logger.info("[Search] Step 1: Opening search bar...")
    _t0 = time.time()
    opened = home.open_search()
    _t1 = time.time()
    logger.info(
        "[Search] Step 1 complete — search bar %s | elapsed: %.2f s",
        "opened" if opened else "NOT found (will attempt type anyway)",
        _t1 - _t0,
    )

    # ── Step 2: Type keyword ──────────────────────────────────────────────────
    logger.info("[Search] Step 2: Typing keyword 'Bollywood'...")
    _t2 = time.time()
    home.perform_search("Bollywood")
    _t3 = time.time()
    logger.info(
        "[Search] Step 2 complete — keyword filled + Enter pressed | elapsed: %.2f s",
        _t3 - _t2,
    )

    # ── Step 3: Wait for search results page ──────────────────────────────────
    # bombaytimes redirects to /searchresults?search=<kw> — match on URL pattern.
    # No selector loops, no hardcoded sleep, no network-response gate.
    logger.info("[Search] Step 3: Waiting for search results URL...")
    _t4 = time.time()
    results_found = False
    try:
        page.wait_for_url("**/searchresults**", timeout=10000)
        results_found = True
    except Exception:
        # Fallback: accept any URL that contains 'search' in the path/query
        current_url = page.url.lower()
        if "search" in current_url or "?s=" in current_url or "q=" in current_url:
            results_found = True
            logger.info("[Search] Step 3: URL pattern fallback matched: %s", page.url)
    _t5 = time.time()
    logger.info(
        "[Search] Step 3 complete — results %s | elapsed: %.2f s",
        "FOUND" if results_found else "NOT FOUND",
        _t5 - _t4,
    )

    total_elapsed = _t5 - _t0
    logger.info(
        "[Search] TOTAL elapsed — open: %.2f s | type: %.2f s | results: %.2f s | TOTAL: %.2f s",
        _t1 - _t0, _t3 - _t2, _t5 - _t4, total_elapsed,
    )

    assert results_found, (
        f"Search results page not reached after typing 'Bollywood'. "
        f"Current URL: {page.url}"
    )
    logger.info("PASS: Search results found. URL: %s", page.url)

    home.click_logo()
    expect(page).to_have_url("https://www.bombaytimes.com/", timeout=10000)
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_search_flow ===")
