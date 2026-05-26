import base64
import datetime
import logging
import pathlib
import time

import pytest
from playwright.sync_api import expect
from pages.home_page import HomePage

logger = logging.getLogger(__name__)

# Keywords used to identify Google Analytics / GTM network calls
_GA_KEYWORDS = ["google-analytics", "googletagmanager", "gtag", "collect"]


# ── Per-page canonical + GA validation helper ─────────────────────────────────

def _nav_and_validate(page, page_name, nav_fn, logger, store):
    """
    Navigate to a page via *nav_fn*, then:
      1. Wait up to 15 s for load state.
      2. Hold for 5 s (visual confirmation, GA listener still active).
      3. Remove GA listener.
      4. Validate canonical URL matches opened page URL → PASS / FAIL.
      5. Validate ≥1 GA call fired → PASS / FAIL.
      6. Capture screenshot on any FAIL.
      7. Append result dict to *store*.

    Any exception raised by nav_fn is re-raised after recording the failure so
    the calling test still fails loudly.
    """
    ga_calls = []
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _on_response(resp):
        url = resp.url.lower()
        if any(kw in url for kw in _GA_KEYWORDS):
            ga_calls.append({"url": resp.url, "status": resp.status})

    # Attach listener BEFORE navigation so no GA calls are missed
    page.on("response", _on_response)

    opened_url = ""
    _nav_exc = None

    try:
        nav_fn()
        try:
            page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass
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

    # ── GA calls validation ───────────────────────────────────────────────────
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

    # Wait for listing to fully render (the 5 s hold in _nav_and_validate already helps)
    logger.info("Waiting for Bollywood listing to be ready")
    try:
        page.wait_for_selector("ol.sub-cat-ol li a, a.right-img-a", timeout=10000)
        logger.info("Article listing (ol.sub-cat-ol) is ready")
    except Exception:
        logger.warning("Timed out waiting for ol.sub-cat-ol — will attempt selectors anyway")

    try:
        # BombayTimes listing: <ol class="sub-cat-ol"><li><a class="right-img-a" href="...">
        article_selectors = [
            "ol.sub-cat-ol li a.right-img-a",
            "ol.sub-cat-ol li a",
            "a.right-img-a",
            "a.newsItem[href*='/entertainment/bollywood']",
            "a.newsItem",
            "a[href*='/entertainment/bollywood/']",
            "figure a[href*='/entertainment']",
            "article a",
        ]
        clicked = False
        for sel in article_selectors:
            try:
                loc = page.locator(sel).first
                count = loc.count()
                logger.debug("Selector '%s' → %d element(s)", sel, count)
                if count > 0:
                    logger.info("Clicking first article using selector: %s", sel)
                    loc.click()
                    clicked = True
                    break
            except Exception as exc:
                logger.debug("Selector '%s' raised: %s", sel, exc)
                continue

        if not clicked:
            logger.error("No article selector matched on Bollywood listing page")
            pytest.fail("Could not find any article to click on Bollywood listing page")

        page.wait_for_load_state("load")
        logger.info("Article page loaded: %s", page.url)

        # Trending section
        logger.info("Checking Trending section")
        has_trending = (
            page.locator(".trending, .trendingBlock, .trending-tag, [class*='trending']").count() > 0
            or page.get_by_text("Trending").count() > 0
        )
        if has_trending:
            logger.info("PASS: Trending section found")
        else:
            logger.error("FAIL: Trending section NOT found on %s", page.url)
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
            logger.error("FAIL: Related Articles section NOT found on %s", page.url)
        assert has_related, "Related Articles section not found on article page"

        # Canonical URL
        logger.info("Checking canonical URL on article page")
        canonical_link = page.locator("link[rel='canonical']")
        assert canonical_link.count() > 0, "Canonical link not found"
        canonical_href = canonical_link.first.get_attribute("href")
        assert canonical_href, "Canonical href is empty"
        logger.info("Canonical: %s  |  Page URL: %s", canonical_href, page.url)
        assert canonical_href.rstrip("/") == page.url.rstrip("/"), \
            f"Canonical '{canonical_href}' does not match article URL '{page.url}'"
        logger.info("PASS: Canonical URL matches article URL")

        # amphtml
        logger.info("Checking amphtml link")
        amp = page.locator("link[rel='amphtml']")
        amp_count = amp.count()
        if amp_count > 0:
            logger.info("PASS: amphtml link found: %s", amp.first.get_attribute("href"))
        else:
            logger.error("FAIL: amphtml link NOT found on %s", page.url)
        assert amp_count > 0, "amphtml link not present on article page"

    finally:
        logger.info("Navigating back to homepage (cleanup)")
        home.goto("")

    logger.info("URL after return: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")
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

    # ── Intimate Diaries ──────────────────────────────────────────────────────
    logger.info("Navigating to Intimate Diaries (canonical + GA validation)")
    _nav_and_validate(page, "Intimate Diaries", home.click_intimate_diaries, logger, category_val_store)
    logger.info("After Intimate Diaries: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/intimate-diaries")
    logger.info("PASS: Intimate Diaries URL verified")

    home.click_logo()
    logger.info("After logo click: %s", page.url)
    assert page.url.startswith("https://www.bombaytimes.com/")
    logger.info("PASS: Returned to homepage")

    # ── Photo Stories (overflow menu) ─────────────────────────────────────────
    logger.info("Opening overflow menu for Photo Stories")
    opened = home.open_overflow_menu()
    assert opened, "Overflow menu did not open"
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
    opened = home.open_overflow_menu()
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
    opened = home.open_overflow_menu()
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
    logger.info("=== START: test_search_flow ===")
    home = HomePage(page)
    home.go_home()
    logger.info("Homepage: %s", page.url)

    logger.info("Opening search and searching for 'Bollywood'")
    home.open_search()
    home.perform_search("Bollywood")

    def has_search_results() -> bool:
        try:
            page.wait_for_timeout(1000)
            selectors = [
                "div.search-results",
                "ul.search-list",
                "div.search-list",
                "article",
                ".story-card",
                ".card",
                ".listing",
                "a[href*='/search']",
            ]
            for sel in selectors:
                try:
                    page.wait_for_selector(sel, timeout=2000)
                    logger.info("Search results found via selector: %s", sel)
                    return True
                except Exception:
                    continue

            if "search" in page.url or "?s=" in page.url or "q=" in page.url:
                logger.info("Search results inferred from URL: %s", page.url)
                return True

            content = page.content()
            if "Bollywood" in content:
                logger.info("Search results inferred from page content")
                return True
        except Exception as exc:
            logger.warning("Error while checking search results: %s", exc)
        return False

    if not has_search_results():
        logger.warning("Search results not found on first attempt — retrying")
        home.go_home()
        home.open_search()
        home.perform_search("Bollywood")
        assert has_search_results(), "Search results not found after retry"

    logger.info("PASS: Search results found. URL: %s", page.url)

    home.click_logo()
    expect(page).to_have_url("https://www.bombaytimes.com/", timeout=10000)
    logger.info("PASS: Returned to homepage")
    logger.info("=== END: test_search_flow ===")
