import os
import sys
import base64
import datetime
import pathlib
import platform
import pytest
from playwright.sync_api import sync_playwright

# ── HTML escape helper ────────────────────────────────────────────────────────
def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ── Session-level data stores ─────────────────────────────────────────────────
_ga_store_key          = pytest.StashKey()
_cat_store_key         = pytest.StashKey()
_amp_store_key              = pytest.StashKey()
_photo_amp_store_key        = pytest.StashKey()
_bt_picks_amp_store_key     = pytest.StashKey()
_intimate_diaries_amp_store_key = pytest.StashKey()
_festival_amp_store_key         = pytest.StashKey()
_astro_trends_amp_store_key     = pytest.StashKey()
_sitemap_rss_store_key          = pytest.StashKey()

_session: dict = {
    "tests": [],
    "start_time": None,
    "env": {},
}


# ── Pytest hooks & fixtures ───────────────────────────────────────────────────

def pytest_configure(config):
    pathlib.Path("reports").mkdir(exist_ok=True)
    pathlib.Path(".test-artifacts").mkdir(exist_ok=True)
    _session["start_time"] = datetime.datetime.now()
    _session["env"] = {
        "Project": "BombayTimes Automation",
        "Base URL": "https://www.bombaytimes.com",
        "Browser": "Chromium (headed)",
        "OS": platform.platform(),
        "Python": sys.version.split()[0],
        "Pytest": pytest.__version__,
        "Report Generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        from pytest_metadata.plugin import metadata_key
        for k, v in _session["env"].items():
            config.stash[metadata_key][k] = v
    except Exception:
        pass


@pytest.fixture(scope="session")
def ga_report_store(request):
    """Session fixture that the GA test writes into; conftest reads it for the report."""
    store = {
        "url": "https://www.bombaytimes.com",
        "calls": [],
        "total": 0,
        "passed": None,
        "failed_calls": [],
    }
    request.session.stash[_ga_store_key] = store
    return store


@pytest.fixture(scope="session")
def category_val_store(request):
    """Session fixture that stores per-page canonical & GA validation results.

    Each test that calls _nav_and_validate() appends a result dict here.
    conftest reads it in pytest_sessionfinish to build the HTML report section.
    """
    store = []
    request.session.stash[_cat_store_key] = store
    return store


@pytest.fixture(scope="session")
def bt_picks_amp_report_store(request):
    """Session fixture for BT Picks AMP page validation results."""
    store = {
        "run": False,
        "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    }
    request.session.stash[_bt_picks_amp_store_key] = store
    return store


@pytest.fixture(scope="session")
def intimate_diaries_amp_report_store(request):
    """Session fixture for Intimate Diaries AMP page validation results."""
    store = {
        "run": False,
        "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    }
    request.session.stash[_intimate_diaries_amp_store_key] = store
    return store


@pytest.fixture(scope="session")
def festival_amp_report_store(request):
    """Session fixture for Festival AMP page validation results."""
    store = {
        "run": False,
        "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    }
    request.session.stash[_festival_amp_store_key] = store
    return store


@pytest.fixture(scope="session")
def astro_trends_amp_report_store(request):
    """Session fixture for Astro Trends AMP page validation results."""
    store = {
        "run": False,
        "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    }
    request.session.stash[_astro_trends_amp_store_key] = store
    return store


@pytest.fixture(scope="session")
def sitemap_rss_report_store(request):
    """Session fixture for Sitemap and RSS Feed validation results."""
    store = {
        "run": False,
        "results": [],
        "total": 0,
        "passed": 0,
        "failed": 0,
        "all_sitemaps_ok": False,
        "all_rss_ok": False,
        "summary_message": "",
    }
    request.session.stash[_sitemap_rss_store_key] = store
    return store


@pytest.fixture(scope="session")
def photo_amp_report_store(request):
    """Session fixture for PhotoStory AMP page validation results."""
    store = {
        "run": False,
        "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    }
    request.session.stash[_photo_amp_store_key] = store
    return store


@pytest.fixture(scope="session")
def amp_report_store(request):
    """Session fixture for AMP page validation results.

    Written by test_amp_page_validation; read by conftest to build the
    dedicated AMP Page Validation HTML report section.
    """
    store = {
        "run": False,
        "article_url": "",
        "amp_url": "",
        "page_open": None,
        "canonical_result": None,
        "canonical_url": "",
        "canonical_error": "",
        "amp_error_status": None,
        "amp_errors": [],
        "ga_calls": [],
        "ga_result": None,
        "ga_error": "",
        "overall": None,
    }
    request.session.stash[_amp_store_key] = store
    return store


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance):
    chrome_env = os.environ.get("CHROME_PATH")
    common_paths = [
        chrome_env,
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Chromium\Application\chrome.exe",
    ]
    exe = None
    for p in common_paths:
        if not p:
            continue
        if os.path.exists(p):
            exe = p
            break
    b = (
        playwright_instance.chromium.launch(executable_path=exe, headless=False)
        if exe
        else playwright_instance.chromium.launch(headless=False)
    )
    yield b
    b.close()


@pytest.fixture(scope="session")
def page(browser):
    context = browser.new_context()
    pg = context.new_page()
    yield pg
    try:
        context.close()
    except Exception:
        pass


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()

    if rep.when != "call":
        return

    screenshot_b64 = None
    pg = item.funcargs.get("page")

    if rep.failed and pg:
        artifacts = pathlib.Path(".test-artifacts")
        png_path = artifacts / f"{item.name}_.png"
        html_path = artifacts / f"{item.name}_.html"
        try:
            pg.screenshot(path=str(png_path), full_page=True)
            with open(str(png_path), "rb") as fh:
                screenshot_b64 = base64.b64encode(fh.read()).decode()
        except Exception:
            pass
        try:
            html_path.write_text(pg.content(), encoding="utf-8")
        except Exception:
            pass

    log_output = "\n".join(
        content
        for name, content in rep.sections
        if "log" in name.lower()
    )

    error_msg = str(rep.longrepr) if (rep.failed and rep.longrepr) else ""

    _session["tests"].append({
        "name": item.name,
        "outcome": rep.outcome,
        "duration": round(rep.duration, 2),
        "error": error_msg,
        "logs": log_output,
        "screenshot_b64": screenshot_b64,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


def pytest_sessionfinish(session, exitstatus):
    end_time = datetime.datetime.now()
    start_time = _session["start_time"] or end_time
    duration = round((end_time - start_time).total_seconds(), 1)

    tests = _session["tests"]
    passed = sum(1 for t in tests if t["outcome"] == "passed")
    failed = sum(1 for t in tests if t["outcome"] == "failed")
    skipped = sum(1 for t in tests if t["outcome"] == "skipped")

    ga_data = session.stash.get(_ga_store_key, {
        "url": "https://www.bombaytimes.com",
        "calls": [],
        "total": 0,
        "passed": None,
        "failed_calls": [],
    })

    cat_data = session.stash.get(_cat_store_key, [])

    amp_data = session.stash.get(_amp_store_key, {
        "run": False, "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    })

    photo_amp_data = session.stash.get(_photo_amp_store_key, {
        "run": False, "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    })

    bt_picks_amp_data = session.stash.get(_bt_picks_amp_store_key, {
        "run": False, "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    })

    intimate_diaries_amp_data = session.stash.get(_intimate_diaries_amp_store_key, {
        "run": False, "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    })

    festival_amp_data = session.stash.get(_festival_amp_store_key, {
        "run": False, "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    })

    astro_trends_amp_data = session.stash.get(_astro_trends_amp_store_key, {
        "run": False, "article_url": "", "amp_url": "", "page_open": None,
        "canonical_result": None, "canonical_url": "", "canonical_error": "",
        "amp_error_status": None, "amp_errors": [],
        "ga_calls": [], "ga_result": None, "ga_error": "", "overall": None,
    })

    sitemap_rss_data = session.stash.get(_sitemap_rss_store_key, {
        "run": False, "results": [], "total": 0, "passed": 0, "failed": 0,
        "all_sitemaps_ok": False, "all_rss_ok": False, "summary_message": "",
    })

    _write_report(
        tests=tests,
        passed=passed,
        failed=failed,
        skipped=skipped,
        duration=duration,
        start_time=start_time,
        end_time=end_time,
        ga=ga_data,
        cat_pages=cat_data,
        amp=amp_data,
        photo_amp=photo_amp_data,
        bt_picks_amp=bt_picks_amp_data,
        intimate_diaries_amp=intimate_diaries_amp_data,
        festival_amp=festival_amp_data,
        astro_trends_amp=astro_trends_amp_data,
        sitemap_rss=sitemap_rss_data,
    )


# ── Custom HTML report generator ──────────────────────────────────────────────

def _write_report(tests, passed, failed, skipped, duration, start_time, end_time, ga, cat_pages=None, amp=None, photo_amp=None, bt_picks_amp=None, intimate_diaries_amp=None, festival_amp=None, astro_trends_amp=None, sitemap_rss=None):
    cat_pages             = cat_pages             or []
    amp                   = amp                   or {}
    photo_amp             = photo_amp             or {}
    bt_picks_amp          = bt_picks_amp          or {}
    intimate_diaries_amp  = intimate_diaries_amp  or {}
    festival_amp          = festival_amp          or {}
    astro_trends_amp      = astro_trends_amp      or {}
    sitemap_rss           = sitemap_rss           or {}
    total = len(tests)
    pass_rate = round((passed / total * 100) if total else 0, 1)
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
    run_ok = failed == 0

    # ── CSS (plain string — no f-string escaping needed) ─────────────────────
    css = """
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:#f0f2f5;color:#333;font-size:14px}

    /* Header */
    .hdr{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 55%,#0f3460 100%);color:#fff;padding:22px 40px;display:flex;justify-content:space-between;align-items:center}
    .hdr-left h1{font-size:22px;font-weight:700;letter-spacing:.3px;margin-top:6px}
    .hdr-left p{font-size:12px;color:#9fa8b5;margin-top:4px}
    .run-pill{display:inline-block;padding:4px 14px;border-radius:20px;font-size:12px;font-weight:700}
    .pill-ok{background:#28a745;color:#fff}
    .pill-fail{background:#dc3545;color:#fff}
    .hdr-right{text-align:right;font-size:12px;color:#9fa8b5;line-height:2}

    /* Summary cards */
    .cards{display:grid;grid-template-columns:repeat(6,1fr);gap:14px;padding:24px 40px}
    .card{background:#fff;border-radius:10px;padding:18px 12px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.07)}
    .cv{font-size:30px;font-weight:700;line-height:1.1}
    .cl{font-size:11px;color:#6c757d;text-transform:uppercase;letter-spacing:.6px;margin-top:5px}
    .c-tot .cv{color:#495057}
    .c-pas .cv{color:#28a745}
    .c-fai .cv{color:#dc3545}
    .c-ski .cv{color:#fd7e14}
    .c-rat .cv{color:#0d6efd}
    .c-dur .cv{font-size:20px;color:#6f42c1}

    /* Progress */
    .prog-wrap{margin:0 40px 22px;background:#fff;border-radius:8px;padding:16px 20px;box-shadow:0 2px 8px rgba(0,0,0,.07)}
    .prog-lbl{font-size:12px;color:#6c757d;margin-bottom:6px}
    .prog-bar{background:#e9ecef;border-radius:20px;height:14px;overflow:hidden}
    .prog-fill{height:100%;border-radius:20px;background:linear-gradient(90deg,#28a745,#20c997);transition:width .4s}

    /* Generic section */
    .sec{background:#fff;border-radius:10px;margin:0 40px 22px;padding:22px 24px;box-shadow:0 2px 8px rgba(0,0,0,.07)}
    .sec-title{font-size:15px;font-weight:700;color:#343a40;border-bottom:2px solid #f0f0f0;padding-bottom:10px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between}

    /* Environment */
    .env-tbl{width:100%;border-collapse:collapse;font-size:13px}
    .env-tbl tr:nth-child(even){background:#f8f9fa}
    .env-tbl td{padding:8px 14px;border-bottom:1px solid #f0f0f0}
    .env-key{font-weight:600;color:#495057;width:220px}

    /* GA section */
    .ga-chips{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
    .chip{background:#f8f9fa;border:1px solid #e9ecef;border-radius:8px;padding:10px 16px;min-width:160px}
    .chip-lbl{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#6c757d;margin-bottom:3px}
    .chip-val{font-size:13px;font-weight:600;color:#343a40;word-break:break-all}
    .ga-tbl{width:100%;border-collapse:collapse;font-size:12px;margin-top:4px}
    .ga-tbl thead th{background:#343a40;color:#fff;padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
    .ga-tbl tbody tr:nth-child(even){background:#f8f9fa}
    .ga-tbl td{padding:7px 12px;border-bottom:1px solid #e9ecef;vertical-align:top}
    .ga-num{width:40px;text-align:center;color:#6c757d}
    .ga-url{font-family:'Courier New',monospace;color:#0d6efd;font-size:11px;word-break:break-all}
    .http{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}
    .http-ok{background:#d4edda;color:#155724}
    .http-err{background:#f8d7da;color:#721c24}
    .no-data{color:#6c757d;font-style:italic;padding:10px 0;font-size:13px}
    .sub-lbl{font-size:12px;font-weight:600;color:#495057;text-transform:uppercase;letter-spacing:.4px;margin-bottom:8px}

    /* Results table */
    .res-tbl{width:100%;border-collapse:collapse;font-size:13px}
    .res-tbl thead th{background:#343a40;color:#fff;padding:10px 14px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
    .trow{cursor:pointer;border-left:4px solid transparent;transition:background .12s}
    .trow:hover{background:#f8f9fa}
    .trow-passed{border-left-color:#28a745}
    .trow-failed{border-left-color:#dc3545}
    .trow-skipped{border-left-color:#fd7e14}
    .res-tbl td{padding:9px 14px;border-bottom:1px solid #e9ecef;vertical-align:middle}
    .td-num{color:#adb5bd;width:36px;text-align:center;font-size:12px}
    .td-name{font-weight:500}
    .td-dur{color:#6c757d;width:80px;font-size:12px}
    .td-ts{color:#6c757d;width:160px;font-size:11px}
    .td-err{max-width:260px}
    .td-exp{width:28px;text-align:center;color:#adb5bd;font-size:11px}
    .err-prev{color:#dc3545;font-size:11px;font-family:'Courier New',monospace;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}
    .badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;letter-spacing:.4px}
    .b-passed{background:#d4edda;color:#155724}
    .b-failed{background:#f8d7da;color:#721c24}
    .b-skipped{background:#fff3cd;color:#856404}

    /* Expandable detail */
    .drow{display:none}
    .drow.open{display:table-row}
    .dtd{background:#f5f6f8;padding:16px 24px}
    .dlbl{font-size:11px;font-weight:700;color:#495057;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
    .dsec{margin-bottom:14px}
    .log-blk{background:#1e2029;color:#abb2bf;padding:12px 16px;border-radius:6px;font-family:'Courier New',monospace;font-size:11px;max-height:320px;overflow-y:auto;white-space:pre-wrap;line-height:1.55}
    .err-blk{background:#fff5f5;border:1px solid #f8d7da;border-radius:6px;padding:12px 16px;font-family:'Courier New',monospace;font-size:11px;color:#721c24;white-space:pre-wrap;max-height:260px;overflow-y:auto}
    .ss-img{max-width:100%;border:1px solid #dee2e6;border-radius:6px;margin-top:8px;max-height:480px}

    /* AMP section */
    .amp-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
    .amp-item{background:#f8f9fa;border:1px solid #e9ecef;border-radius:8px;padding:12px 14px}
    .amp-item-lbl{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#6c757d;margin-bottom:4px}
    .amp-item-val{font-size:12px;font-weight:600;color:#343a40;word-break:break-all}
    .amp-url{font-family:'Courier New',monospace;font-size:11px;color:#0d6efd;word-break:break-all}
    .amp-errors{background:#fff5f5;border:1px solid #f8d7da;border-radius:6px;padding:10px 14px;
                font-family:'Courier New',monospace;font-size:11px;color:#721c24;margin-top:8px}
    .amp-err-line{padding:2px 0;border-bottom:1px dotted #f8d7da}
    .amp-err-line:last-child{border-bottom:none}

    /* Sitemap / RSS section */
    .sm-tbl{width:100%;border-collapse:collapse;font-size:12px;margin-top:4px}
    .sm-tbl thead th{background:#343a40;color:#fff;padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
    .sm-tbl tbody tr:nth-child(even){background:#f8f9fa}
    .sm-tbl td{padding:7px 12px;border-bottom:1px solid #e9ecef;vertical-align:middle}
    .sm-url{font-family:'Courier New',monospace;font-size:11px;color:#0d6efd;word-break:break-all}
    .sm-type-sitemap{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;background:#e3f2fd;color:#0d47a1}
    .sm-type-rss{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;background:#fff3e0;color:#e65100}
    .sm-summary{border-radius:6px;padding:12px 16px;font-size:13px;font-weight:600;margin-top:16px;text-align:center}
    .sm-summary-ok{background:#d4edda;border:1px solid #c3e6cb;color:#155724}
    .sm-summary-fail{background:#f8d7da;border:1px solid #f5c6cb;color:#721c24}
    .sm-chips{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}

    /* Footer */
    .footer{text-align:center;padding:20px 40px 30px;color:#adb5bd;font-size:12px}
    """

    # ── JavaScript ────────────────────────────────────────────────────────────
    js = """
    function toggle(id) {
        var el = document.getElementById(id);
        if (!el) return;
        el.classList.toggle('open');
        var prev = el.previousElementSibling;
        if (prev) {
            var exp = prev.querySelector('.td-exp');
            if (exp) exp.textContent = el.classList.contains('open') ? '▲' : '▼';
        }
    }
    """

    # ── Environment rows ──────────────────────────────────────────────────────
    env_rows = "".join(
        f"<tr><td class='env-key'>{_esc(k)}</td><td>{_esc(str(v))}</td></tr>"
        for k, v in _session["env"].items()
    )

    # ── GA section ────────────────────────────────────────────────────────────
    ga_passed = ga.get("passed")
    ga_total  = ga.get("total", 0)
    ga_url    = ga.get("url", "https://www.bombaytimes.com")
    ga_calls  = ga.get("calls", [])
    ga_failed = ga.get("failed_calls", [])

    if ga_passed is True:
        ga_badge = '<span class="badge b-passed">✓ PASSED</span>'
        ga_status_txt = "All GA calls validated successfully"
    elif ga_passed is False:
        ga_badge = '<span class="badge b-failed">✗ FAILED</span>'
        ga_status_txt = f"{len(ga_failed)} call(s) returned unexpected status"
    else:
        ga_badge = '<span class="badge b-skipped">— N/A</span>'
        ga_status_txt = "GA validation test was not executed"

    if ga_calls:
        ga_rows = ""
        for i, e in enumerate(ga_calls, 1):
            cls = "http-ok" if e["status"] in (200, 204) else "http-err"
            ga_rows += (
                f"<tr>"
                f"<td class='ga-num'>{i}</td>"
                f"<td><span class='http {cls}'>{e['status']}</span></td>"
                f"<td class='ga-url'>{_esc(e['url'])}</td>"
                f"</tr>"
            )
        ga_calls_html = (
            "<table class='ga-tbl'>"
            "<thead><tr><th>#</th><th>HTTP</th><th>Request URL</th></tr></thead>"
            f"<tbody>{ga_rows}</tbody></table>"
        )
    else:
        ga_calls_html = "<div class='no-data'>No GA network calls were captured.</div>"

    # ── Category / subcategory page validation section ────────────────────────
    cat_total    = len(cat_pages)
    cat_can_pass = sum(1 for p in cat_pages if p.get("canonical_status") == "PASS")
    cat_can_fail = sum(1 for p in cat_pages if p.get("canonical_status") == "FAIL")
    cat_ga_pass  = sum(1 for p in cat_pages if p.get("ga_status") == "PASS")
    cat_ga_fail  = sum(1 for p in cat_pages if p.get("ga_status") == "FAIL")

    if cat_pages:
        cat_rows_html = ""
        for i, p in enumerate(cat_pages):
            can_ok  = p.get("canonical_status") == "PASS"
            ga_ok   = p.get("ga_status") == "PASS"
            row_ok  = can_ok and ga_ok
            can_cls = "b-passed" if can_ok else "b-failed"
            ga_cls  = "b-passed" if ga_ok  else "b-failed"
            row_can_badge = f"<span class='badge {can_cls}'>{p.get('canonical_status','—')}</span>"
            row_ga_badge  = f"<span class='badge {ga_cls}'>{p.get('ga_status','—')}</span>"

            # Combine any error messages
            err_parts = []
            if p.get("canonical_error"):
                err_parts.append(_esc(p["canonical_error"]))
            if p.get("ga_error"):
                err_parts.append(_esc(p["ga_error"]))
            err_cell = "<br>".join(err_parts) if err_parts else ""

            # AMP column — only present if AMP validation ran for this page
            amp_overall_val = p.get("amp_overall")
            if amp_overall_val == "PASS":
                amp_cell = "<span class='badge b-passed'>&#10003; AMP</span>"
            elif amp_overall_val == "FAIL":
                amp_cell = "<span class='badge b-failed'>&#10007; AMP</span>"
            else:
                amp_cell = "<span style='color:#adb5bd;font-size:11px'>&#8212;</span>"

            # Screenshot toggle
            ss = p.get("screenshot_b64")
            detail_id = f"cv{i}"
            expand_td = ""
            ss_row    = ""
            if ss:
                expand_td = f"<td class='td-exp' style='cursor:pointer'>&#x25BC;</td>"
                ss_row = (
                    f"<tr class='drow' id='{detail_id}'>"
                    f"<td colspan='10' class='dtd'>"
                    f"<div class='dsec'>"
                    f"<div class='dlbl'>Screenshot (captured on FAIL)</div>"
                    f"<img src='data:image/png;base64,{ss}' class='ss-img'>"
                    f"</div></td></tr>"
                )
            else:
                expand_td = "<td></td>"

            row_cls   = "trow-passed" if row_ok else "trow-failed"
            click_attr = f" onclick=\"toggle('{detail_id}')\" style='cursor:pointer'" if ss else ""

            cat_rows_html += (
                f"<tr class='trow {row_cls}'{click_attr}>"
                f"<td class='td-num'>{i + 1}</td>"
                f"<td class='td-name'>{_esc(p.get('page_name', ''))}</td>"
                f"<td style='font-family:\"Courier New\",monospace;font-size:11px;word-break:break-all;max-width:200px'>"
                f"{_esc(p.get('opened_url', ''))}</td>"
                f"<td style='font-family:\"Courier New\",monospace;font-size:11px;word-break:break-all;max-width:200px'>"
                f"{_esc(p.get('canonical_href', ''))}</td>"
                f"<td>{row_can_badge}</td>"
                f"<td>{row_ga_badge}</td>"
                f"<td>{amp_cell}</td>"
                f"<td style='color:#dc3545;font-size:11px'>{err_cell}</td>"
                f"<td class='td-ts'>{_esc(p.get('timestamp', ''))}</td>"
                f"{expand_td}"
                f"</tr>"
            )
            cat_rows_html += ss_row

        cat_section_body = (
            "<table class='res-tbl' style='font-size:12px'>"
            "<thead><tr>"
            "<th>#</th><th>Page Name</th><th>Opened URL</th><th>Canonical URL</th>"
            "<th>Canonical</th><th>GA</th><th>AMP</th><th>Error / Note</th><th>Timestamp</th><th></th>"
            "</tr></thead>"
            f"<tbody>{cat_rows_html}</tbody></table>"
        )
    else:
        cat_section_body = "<div class='no-data'>No category page validations were recorded.</div>"

    # ── AMP page validation section ───────────────────────────────────────────
    amp_ran          = amp.get("run", False)
    amp_overall      = amp.get("overall")
    amp_article_url  = amp.get("article_url", "")
    amp_url_val      = amp.get("amp_url", "")
    amp_page_open    = amp.get("page_open")
    amp_can_result   = amp.get("canonical_result")
    amp_can_url      = amp.get("canonical_url", "")
    amp_can_error    = amp.get("canonical_error", "")
    amp_err_status   = amp.get("amp_error_status")
    amp_errors_list  = amp.get("amp_errors", [])
    amp_ga_calls     = amp.get("ga_calls", [])
    amp_ga_result    = amp.get("ga_result")
    amp_ga_error     = amp.get("ga_error", "")

    def _amp_badge(val):
        if val == "PASS":
            return "<span class='badge b-passed'>&#10003; PASS</span>"
        if val == "FAIL":
            return "<span class='badge b-failed'>&#10007; FAIL</span>"
        return "<span class='badge b-skipped'>&#8212; N/A</span>"

    if not amp_ran:
        amp_section_body = "<div class='no-data'>AMP validation test was not executed in this run.</div>"
        amp_overall_badge = _amp_badge(None)
    else:
        amp_open_badge = _amp_badge("PASS" if amp_page_open else "FAIL")
        amp_can_badge  = _amp_badge(amp_can_result)
        amp_err_badge  = _amp_badge(amp_err_status)
        amp_ga_badge   = _amp_badge(amp_ga_result)
        amp_overall_badge = _amp_badge(amp_overall)

        # GA rows for AMP
        if amp_ga_calls:
            amp_ga_rows = ""
            for i, e in enumerate(amp_ga_calls, 1):
                cls = "http-ok" if e["status"] in (200, 204) else "http-err"
                amp_ga_rows += (
                    f"<tr><td class='ga-num'>{i}</td>"
                    f"<td><span class='http {cls}'>{e['status']}</span></td>"
                    f"<td class='ga-url'>{_esc(e['url'])}</td></tr>"
                )
            amp_ga_html = (
                "<table class='ga-tbl' style='margin-top:8px'>"
                "<thead><tr><th>#</th><th>HTTP</th><th>Request URL</th></tr></thead>"
                f"<tbody>{amp_ga_rows}</tbody></table>"
            )
        else:
            amp_ga_html = f"<div class='no-data'>{_esc(amp_ga_error) if amp_ga_error else 'No GA calls captured.'}</div>"

        # AMP error detail block
        if amp_errors_list:
            err_lines = "".join(
                f"<div class='amp-err-line'>{_esc(e)}</div>" for e in amp_errors_list
            )
            amp_errors_html = f"<div class='amp-errors'>{err_lines}</div>"
        else:
            amp_errors_html = "<div style='color:#28a745;font-size:12px;margin-top:4px'>No AMP validation errors detected.</div>"

        amp_section_body = f"""
<div class="amp-grid">
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">Article URL (Normal)</div>
    <div class="amp-url">{_esc(amp_article_url)}</div>
  </div>
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">AMP URL Tested</div>
    <div class="amp-url">{_esc(amp_url_val)}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Page Opened</div>
    <div class="amp-item-val">{amp_open_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">Canonical Validation</div>
    <div class="amp-item-val">{amp_can_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Error Check</div>
    <div class="amp-item-val">{amp_err_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">GA Tag Validation</div>
    <div class="amp-item-val">{amp_ga_badge}</div>
  </div>
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">Canonical URL (from AMP page)</div>
  <div class="amp-url" style="margin-top:6px">{_esc(amp_can_url) if amp_can_url else '<em style="color:#6c757d">Not found</em>'}</div>
  {(f'<div style="color:#dc3545;font-size:11px;margin-top:4px">{_esc(amp_can_error)}</div>') if amp_can_error else ''}
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">AMP Validation Error Details</div>
  {amp_errors_html}
</div>

<div>
  <div class="sub-lbl">GA Network Requests (AMP Page)</div>
  {amp_ga_html}
</div>
"""

    # ── PhotoStory AMP page validation section ────────────────────────────────
    ps_amp_ran         = photo_amp.get("run", False)
    ps_amp_overall     = photo_amp.get("overall")
    ps_amp_article_url = photo_amp.get("article_url", "")
    ps_amp_url_val     = photo_amp.get("amp_url", "")
    ps_amp_page_open   = photo_amp.get("page_open")
    ps_amp_can_result  = photo_amp.get("canonical_result")
    ps_amp_can_url     = photo_amp.get("canonical_url", "")
    ps_amp_can_error   = photo_amp.get("canonical_error", "")
    ps_amp_err_status  = photo_amp.get("amp_error_status")
    ps_amp_errors_list = photo_amp.get("amp_errors", [])
    ps_amp_ga_calls    = photo_amp.get("ga_calls", [])
    ps_amp_ga_result   = photo_amp.get("ga_result")
    ps_amp_ga_error    = photo_amp.get("ga_error", "")

    if not ps_amp_ran:
        ps_amp_section_body  = "<div class='no-data'>PhotoStory AMP validation was not executed in this run.</div>"
        ps_amp_overall_badge = _amp_badge(None)
    else:
        ps_amp_open_badge   = _amp_badge("PASS" if ps_amp_page_open else "FAIL")
        ps_amp_can_badge    = _amp_badge(ps_amp_can_result)
        ps_amp_err_badge    = _amp_badge(ps_amp_err_status)
        ps_amp_ga_badge_val = _amp_badge(ps_amp_ga_result)
        ps_amp_overall_badge = _amp_badge(ps_amp_overall)

        if ps_amp_ga_calls:
            ps_ga_rows = ""
            for i, e in enumerate(ps_amp_ga_calls, 1):
                cls = "http-ok" if e["status"] in (200, 204) else "http-err"
                ps_ga_rows += (
                    f"<tr><td class='ga-num'>{i}</td>"
                    f"<td><span class='http {cls}'>{e['status']}</span></td>"
                    f"<td class='ga-url'>{_esc(e['url'])}</td></tr>"
                )
            ps_amp_ga_html = (
                "<table class='ga-tbl' style='margin-top:8px'>"
                "<thead><tr><th>#</th><th>HTTP</th><th>Request URL</th></tr></thead>"
                f"<tbody>{ps_ga_rows}</tbody></table>"
            )
        else:
            ps_amp_ga_html = f"<div class='no-data'>{_esc(ps_amp_ga_error) if ps_amp_ga_error else 'No GA calls captured.'}</div>"

        if ps_amp_errors_list:
            ps_err_lines = "".join(
                f"<div class='amp-err-line'>{_esc(e)}</div>" for e in ps_amp_errors_list
            )
            ps_amp_errors_html = f"<div class='amp-errors'>{ps_err_lines}</div>"
        else:
            ps_amp_errors_html = "<div style='color:#28a745;font-size:12px;margin-top:4px'>No AMP validation errors detected.</div>"

        ps_amp_section_body = f"""
<div class="amp-grid">
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">PhotoStory URL (Normal)</div>
    <div class="amp-url">{_esc(ps_amp_article_url)}</div>
  </div>
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">AMP URL Tested</div>
    <div class="amp-url">{_esc(ps_amp_url_val)}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Page Opened</div>
    <div class="amp-item-val">{ps_amp_open_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">Canonical Validation</div>
    <div class="amp-item-val">{ps_amp_can_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Error Check</div>
    <div class="amp-item-val">{ps_amp_err_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">GA Tag Validation</div>
    <div class="amp-item-val">{ps_amp_ga_badge_val}</div>
  </div>
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">Canonical URL (from PhotoStory AMP page)</div>
  <div class="amp-url" style="margin-top:6px">{_esc(ps_amp_can_url) if ps_amp_can_url else '<em style="color:#6c757d">Not found</em>'}</div>
  {(f'<div style="color:#dc3545;font-size:11px;margin-top:4px">{_esc(ps_amp_can_error)}</div>') if ps_amp_can_error else ''}
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">AMP Validation Error Details</div>
  {ps_amp_errors_html}
</div>

<div>
  <div class="sub-lbl">GA Network Requests (PhotoStory AMP Page)</div>
  {ps_amp_ga_html}
</div>
"""

    # ── BT Picks AMP page validation section ─────────────────────────────────
    bt_amp_ran         = bt_picks_amp.get("run", False)
    bt_amp_overall     = bt_picks_amp.get("overall")
    bt_amp_article_url = bt_picks_amp.get("article_url", "")
    bt_amp_url_val     = bt_picks_amp.get("amp_url", "")
    bt_amp_page_open   = bt_picks_amp.get("page_open")
    bt_amp_can_result  = bt_picks_amp.get("canonical_result")
    bt_amp_can_url     = bt_picks_amp.get("canonical_url", "")
    bt_amp_can_error   = bt_picks_amp.get("canonical_error", "")
    bt_amp_err_status  = bt_picks_amp.get("amp_error_status")
    bt_amp_errors_list = bt_picks_amp.get("amp_errors", [])
    bt_amp_ga_calls    = bt_picks_amp.get("ga_calls", [])
    bt_amp_ga_result   = bt_picks_amp.get("ga_result")
    bt_amp_ga_error    = bt_picks_amp.get("ga_error", "")

    if not bt_amp_ran:
        bt_amp_section_body  = "<div class='no-data'>BT Picks AMP validation was not executed in this run.</div>"
        bt_amp_overall_badge = _amp_badge(None)
    else:
        bt_amp_open_badge    = _amp_badge("PASS" if bt_amp_page_open else "FAIL")
        bt_amp_can_badge     = _amp_badge(bt_amp_can_result)
        bt_amp_err_badge     = _amp_badge(bt_amp_err_status)
        bt_amp_ga_badge_val  = _amp_badge(bt_amp_ga_result)
        bt_amp_overall_badge = _amp_badge(bt_amp_overall)

        if bt_amp_ga_calls:
            bt_ga_rows = ""
            for i, e in enumerate(bt_amp_ga_calls, 1):
                cls = "http-ok" if e["status"] in (200, 204) else "http-err"
                bt_ga_rows += (
                    f"<tr><td class='ga-num'>{i}</td>"
                    f"<td><span class='http {cls}'>{e['status']}</span></td>"
                    f"<td class='ga-url'>{_esc(e['url'])}</td></tr>"
                )
            bt_amp_ga_html = (
                "<table class='ga-tbl' style='margin-top:8px'>"
                "<thead><tr><th>#</th><th>HTTP</th><th>Request URL</th></tr></thead>"
                f"<tbody>{bt_ga_rows}</tbody></table>"
            )
        else:
            bt_amp_ga_html = f"<div class='no-data'>{_esc(bt_amp_ga_error) if bt_amp_ga_error else 'No GA calls captured.'}</div>"

        if bt_amp_errors_list:
            bt_err_lines = "".join(
                f"<div class='amp-err-line'>{_esc(e)}</div>" for e in bt_amp_errors_list
            )
            bt_amp_errors_html = f"<div class='amp-errors'>{bt_err_lines}</div>"
        else:
            bt_amp_errors_html = "<div style='color:#28a745;font-size:12px;margin-top:4px'>No AMP validation errors detected.</div>"

        bt_amp_section_body = f"""
<div class="amp-grid">
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">BT Picks Article URL (Normal)</div>
    <div class="amp-url">{_esc(bt_amp_article_url)}</div>
  </div>
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">AMP URL Tested</div>
    <div class="amp-url">{_esc(bt_amp_url_val)}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Page Opened</div>
    <div class="amp-item-val">{bt_amp_open_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">Canonical Validation</div>
    <div class="amp-item-val">{bt_amp_can_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Error Check</div>
    <div class="amp-item-val">{bt_amp_err_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">GA Tag Validation</div>
    <div class="amp-item-val">{bt_amp_ga_badge_val}</div>
  </div>
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">Canonical URL (from BT Picks AMP page)</div>
  <div class="amp-url" style="margin-top:6px">{_esc(bt_amp_can_url) if bt_amp_can_url else '<em style="color:#6c757d">Not found</em>'}</div>
  {(f'<div style="color:#dc3545;font-size:11px;margin-top:4px">{_esc(bt_amp_can_error)}</div>') if bt_amp_can_error else ''}
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">AMP Validation Error Details</div>
  {bt_amp_errors_html}
</div>

<div>
  <div class="sub-lbl">GA Network Requests (BT Picks AMP Page)</div>
  {bt_amp_ga_html}
</div>
"""

    # ── Intimate Diaries AMP page validation section ──────────────────────────
    id_amp_ran         = intimate_diaries_amp.get("run", False)
    id_amp_overall     = intimate_diaries_amp.get("overall")
    id_amp_article_url = intimate_diaries_amp.get("article_url", "")
    id_amp_url_val     = intimate_diaries_amp.get("amp_url", "")
    id_amp_page_open   = intimate_diaries_amp.get("page_open")
    id_amp_can_result  = intimate_diaries_amp.get("canonical_result")
    id_amp_can_url     = intimate_diaries_amp.get("canonical_url", "")
    id_amp_can_error   = intimate_diaries_amp.get("canonical_error", "")
    id_amp_err_status  = intimate_diaries_amp.get("amp_error_status")
    id_amp_errors_list = intimate_diaries_amp.get("amp_errors", [])
    id_amp_ga_calls    = intimate_diaries_amp.get("ga_calls", [])
    id_amp_ga_result   = intimate_diaries_amp.get("ga_result")
    id_amp_ga_error    = intimate_diaries_amp.get("ga_error", "")

    if not id_amp_ran:
        id_amp_section_body  = "<div class='no-data'>Intimate Diaries AMP validation was not executed in this run.</div>"
        id_amp_overall_badge = _amp_badge(None)
    else:
        id_amp_open_badge    = _amp_badge("PASS" if id_amp_page_open else "FAIL")
        id_amp_can_badge     = _amp_badge(id_amp_can_result)
        id_amp_err_badge     = _amp_badge(id_amp_err_status)
        id_amp_ga_badge_val  = _amp_badge(id_amp_ga_result)
        id_amp_overall_badge = _amp_badge(id_amp_overall)

        if id_amp_ga_calls:
            id_ga_rows = ""
            for i, e in enumerate(id_amp_ga_calls, 1):
                cls = "http-ok" if e["status"] in (200, 204) else "http-err"
                id_ga_rows += (
                    f"<tr><td class='ga-num'>{i}</td>"
                    f"<td><span class='http {cls}'>{e['status']}</span></td>"
                    f"<td class='ga-url'>{_esc(e['url'])}</td></tr>"
                )
            id_amp_ga_html = (
                "<table class='ga-tbl' style='margin-top:8px'>"
                "<thead><tr><th>#</th><th>HTTP</th><th>Request URL</th></tr></thead>"
                f"<tbody>{id_ga_rows}</tbody></table>"
            )
        else:
            id_amp_ga_html = f"<div class='no-data'>{_esc(id_amp_ga_error) if id_amp_ga_error else 'No GA calls captured.'}</div>"

        if id_amp_errors_list:
            id_err_lines = "".join(
                f"<div class='amp-err-line'>{_esc(e)}</div>" for e in id_amp_errors_list
            )
            id_amp_errors_html = f"<div class='amp-errors'>{id_err_lines}</div>"
        else:
            id_amp_errors_html = "<div style='color:#28a745;font-size:12px;margin-top:4px'>No AMP validation errors detected.</div>"

        id_amp_section_body = f"""
<div class="amp-grid">
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">Intimate Diaries Article URL (Normal)</div>
    <div class="amp-url">{_esc(id_amp_article_url)}</div>
  </div>
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">AMP URL Tested</div>
    <div class="amp-url">{_esc(id_amp_url_val)}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Page Opened</div>
    <div class="amp-item-val">{id_amp_open_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">Canonical Validation</div>
    <div class="amp-item-val">{id_amp_can_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Error Check</div>
    <div class="amp-item-val">{id_amp_err_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">GA Tag Validation</div>
    <div class="amp-item-val">{id_amp_ga_badge_val}</div>
  </div>
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">Canonical URL (from Intimate Diaries AMP page)</div>
  <div class="amp-url" style="margin-top:6px">{_esc(id_amp_can_url) if id_amp_can_url else '<em style="color:#6c757d">Not found</em>'}</div>
  {(f'<div style="color:#dc3545;font-size:11px;margin-top:4px">{_esc(id_amp_can_error)}</div>') if id_amp_can_error else ''}
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">AMP Validation Error Details</div>
  {id_amp_errors_html}
</div>

<div>
  <div class="sub-lbl">GA Network Requests (Intimate Diaries AMP Page)</div>
  {id_amp_ga_html}
</div>
"""

    # ── Festival AMP page validation section ─────────────────────────────────
    fest_amp_ran         = festival_amp.get("run", False)
    fest_amp_overall     = festival_amp.get("overall")
    fest_amp_article_url = festival_amp.get("article_url", "")
    fest_amp_url_val     = festival_amp.get("amp_url", "")
    fest_amp_page_open   = festival_amp.get("page_open")
    fest_amp_can_result  = festival_amp.get("canonical_result")
    fest_amp_can_url     = festival_amp.get("canonical_url", "")
    fest_amp_can_error   = festival_amp.get("canonical_error", "")
    fest_amp_err_status  = festival_amp.get("amp_error_status")
    fest_amp_errors_list = festival_amp.get("amp_errors", [])
    fest_amp_ga_calls    = festival_amp.get("ga_calls", [])
    fest_amp_ga_result   = festival_amp.get("ga_result")
    fest_amp_ga_error    = festival_amp.get("ga_error", "")

    if not fest_amp_ran:
        fest_amp_section_body  = "<div class='no-data'>Festival AMP validation was not executed in this run.</div>"
        fest_amp_overall_badge = _amp_badge(None)
    else:
        fest_amp_open_badge    = _amp_badge("PASS" if fest_amp_page_open else "FAIL")
        fest_amp_can_badge     = _amp_badge(fest_amp_can_result)
        fest_amp_err_badge     = _amp_badge(fest_amp_err_status)
        fest_amp_ga_badge_val  = _amp_badge(fest_amp_ga_result)
        fest_amp_overall_badge = _amp_badge(fest_amp_overall)

        if fest_amp_ga_calls:
            fest_ga_rows = ""
            for i, e in enumerate(fest_amp_ga_calls, 1):
                cls = "http-ok" if e["status"] in (200, 204) else "http-err"
                fest_ga_rows += (
                    f"<tr><td class='ga-num'>{i}</td>"
                    f"<td><span class='http {cls}'>{e['status']}</span></td>"
                    f"<td class='ga-url'>{_esc(e['url'])}</td></tr>"
                )
            fest_amp_ga_html = (
                "<table class='ga-tbl' style='margin-top:8px'>"
                "<thead><tr><th>#</th><th>HTTP</th><th>Request URL</th></tr></thead>"
                f"<tbody>{fest_ga_rows}</tbody></table>"
            )
        else:
            fest_amp_ga_html = f"<div class='no-data'>{_esc(fest_amp_ga_error) if fest_amp_ga_error else 'No GA calls captured.'}</div>"

        if fest_amp_errors_list:
            fest_err_lines = "".join(
                f"<div class='amp-err-line'>{_esc(e)}</div>" for e in fest_amp_errors_list
            )
            fest_amp_errors_html = f"<div class='amp-errors'>{fest_err_lines}</div>"
        else:
            fest_amp_errors_html = "<div style='color:#28a745;font-size:12px;margin-top:4px'>No AMP validation errors detected.</div>"

        fest_amp_section_body = f"""
<div class="amp-grid">
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">Festival Article URL (Normal)</div>
    <div class="amp-url">{_esc(fest_amp_article_url)}</div>
  </div>
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">AMP URL Tested</div>
    <div class="amp-url">{_esc(fest_amp_url_val)}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Page Opened</div>
    <div class="amp-item-val">{fest_amp_open_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">Canonical Validation</div>
    <div class="amp-item-val">{fest_amp_can_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Error Check</div>
    <div class="amp-item-val">{fest_amp_err_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">GA Tag Validation</div>
    <div class="amp-item-val">{fest_amp_ga_badge_val}</div>
  </div>
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">Canonical URL (from Festival AMP page)</div>
  <div class="amp-url" style="margin-top:6px">{_esc(fest_amp_can_url) if fest_amp_can_url else '<em style="color:#6c757d">Not found</em>'}</div>
  {(f'<div style="color:#dc3545;font-size:11px;margin-top:4px">{_esc(fest_amp_can_error)}</div>') if fest_amp_can_error else ''}
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">AMP Validation Error Details</div>
  {fest_amp_errors_html}
</div>

<div>
  <div class="sub-lbl">GA Network Requests (Festival AMP Page)</div>
  {fest_amp_ga_html}
</div>
"""

    # ── Astro Trends AMP page validation section ──────────────────────────────
    astro_amp_ran         = astro_trends_amp.get("run", False)
    astro_amp_overall     = astro_trends_amp.get("overall")
    astro_amp_article_url = astro_trends_amp.get("article_url", "")
    astro_amp_url_val     = astro_trends_amp.get("amp_url", "")
    astro_amp_page_open   = astro_trends_amp.get("page_open")
    astro_amp_can_result  = astro_trends_amp.get("canonical_result")
    astro_amp_can_url     = astro_trends_amp.get("canonical_url", "")
    astro_amp_can_error   = astro_trends_amp.get("canonical_error", "")
    astro_amp_err_status  = astro_trends_amp.get("amp_error_status")
    astro_amp_errors_list = astro_trends_amp.get("amp_errors", [])
    astro_amp_ga_calls    = astro_trends_amp.get("ga_calls", [])
    astro_amp_ga_result   = astro_trends_amp.get("ga_result")
    astro_amp_ga_error    = astro_trends_amp.get("ga_error", "")

    if not astro_amp_ran:
        astro_amp_section_body  = "<div class='no-data'>Astro Trends AMP validation was not executed in this run.</div>"
        astro_amp_overall_badge = _amp_badge(None)
    else:
        astro_amp_open_badge    = _amp_badge("PASS" if astro_amp_page_open else "FAIL")
        astro_amp_can_badge     = _amp_badge(astro_amp_can_result)
        astro_amp_err_badge     = _amp_badge(astro_amp_err_status)
        astro_amp_ga_badge_val  = _amp_badge(astro_amp_ga_result)
        astro_amp_overall_badge = _amp_badge(astro_amp_overall)

        if astro_amp_ga_calls:
            astro_ga_rows = ""
            for i, e in enumerate(astro_amp_ga_calls, 1):
                cls = "http-ok" if e["status"] in (200, 204) else "http-err"
                astro_ga_rows += (
                    f"<tr><td class='ga-num'>{i}</td>"
                    f"<td><span class='http {cls}'>{e['status']}</span></td>"
                    f"<td class='ga-url'>{_esc(e['url'])}</td></tr>"
                )
            astro_amp_ga_html = (
                "<table class='ga-tbl' style='margin-top:8px'>"
                "<thead><tr><th>#</th><th>HTTP</th><th>Request URL</th></tr></thead>"
                f"<tbody>{astro_ga_rows}</tbody></table>"
            )
        else:
            astro_amp_ga_html = f"<div class='no-data'>{_esc(astro_amp_ga_error) if astro_amp_ga_error else 'No GA calls captured.'}</div>"

        if astro_amp_errors_list:
            astro_err_lines = "".join(
                f"<div class='amp-err-line'>{_esc(e)}</div>" for e in astro_amp_errors_list
            )
            astro_amp_errors_html = f"<div class='amp-errors'>{astro_err_lines}</div>"
        else:
            astro_amp_errors_html = "<div style='color:#28a745;font-size:12px;margin-top:4px'>No AMP validation errors detected.</div>"

        astro_amp_section_body = f"""
<div class="amp-grid">
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">Astro Trends Article URL (Normal)</div>
    <div class="amp-url">{_esc(astro_amp_article_url)}</div>
  </div>
  <div class="amp-item" style="grid-column:span 2">
    <div class="amp-item-lbl">AMP URL Tested</div>
    <div class="amp-url">{_esc(astro_amp_url_val)}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Page Opened</div>
    <div class="amp-item-val">{astro_amp_open_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">Canonical Validation</div>
    <div class="amp-item-val">{astro_amp_can_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">AMP Error Check</div>
    <div class="amp-item-val">{astro_amp_err_badge}</div>
  </div>
  <div class="amp-item">
    <div class="amp-item-lbl">GA Tag Validation</div>
    <div class="amp-item-val">{astro_amp_ga_badge_val}</div>
  </div>
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">Canonical URL (from Astro Trends AMP page)</div>
  <div class="amp-url" style="margin-top:6px">{_esc(astro_amp_can_url) if astro_amp_can_url else '<em style="color:#6c757d">Not found</em>'}</div>
  {(f'<div style="color:#dc3545;font-size:11px;margin-top:4px">{_esc(astro_amp_can_error)}</div>') if astro_amp_can_error else ''}
</div>

<div style="margin-bottom:14px">
  <div class="sub-lbl">AMP Validation Error Details</div>
  {astro_amp_errors_html}
</div>

<div>
  <div class="sub-lbl">GA Network Requests (Astro Trends AMP Page)</div>
  {astro_amp_ga_html}
</div>
"""

    # ── Sitemap and RSS Feed validation section ───────────────────────────────
    sm_ran     = sitemap_rss.get("run", False)
    sm_results = sitemap_rss.get("results", [])
    sm_total   = sitemap_rss.get("total", 0)
    sm_passed  = sitemap_rss.get("passed", 0)
    sm_failed  = sitemap_rss.get("failed", 0)
    sm_sit_ok  = sitemap_rss.get("all_sitemaps_ok", False)
    sm_rss_ok  = sitemap_rss.get("all_rss_ok", False)
    sm_summary = sitemap_rss.get("summary_message", "")

    if not sm_ran:
        sm_overall_badge  = _amp_badge(None)
        sm_section_body   = "<div class='no-data'>Sitemap and RSS Feed validation was not executed in this run.</div>"
        sm_summary_html   = ""
    else:
        sm_overall = "PASS" if sm_failed == 0 and sm_total > 0 else "FAIL"
        sm_overall_badge = _amp_badge(sm_overall)

        # Build table rows
        sm_rows_html = ""
        for i, r in enumerate(sm_results, 1):
            res_cls  = "b-passed" if r["result"] == "PASS" else "b-failed"
            res_badge = f"<span class='badge {res_cls}'>{r['result']}</span>"
            open_badge = (
                "<span class='badge b-passed'>&#10003; Yes</span>"
                if r.get("open_status")
                else "<span class='badge b-failed'>&#10007; No</span>"
            )
            xml_badge = (
                "<span class='badge b-passed'>&#10003; Valid</span>"
                if r.get("xml_valid")
                else "<span class='badge b-failed'>&#10007; Invalid</span>"
            )
            sc = r.get("status_code")
            sc_cls  = "http-ok" if sc == 200 else "http-err"
            sc_html = (
                f"<span class='http {sc_cls}'>{sc}</span>"
                if sc is not None
                else "<span style='color:#adb5bd'>—</span>"
            )
            type_cls  = "sm-type-sitemap" if r["url_type"] == "Sitemap" else "sm-type-rss"
            type_html = f"<span class='{type_cls}'>{_esc(r['url_type'])}</span>"
            err_html  = (
                f"<span style='color:#dc3545;font-size:11px;font-family:\"Courier New\",monospace'>"
                f"{_esc(r['error'])}</span>"
                if r.get("error") else ""
            )
            sm_rows_html += (
                f"<tr>"
                f"<td class='ga-num'>{i}</td>"
                f"<td class='sm-url'>{_esc(r['url'])}</td>"
                f"<td style='white-space:nowrap'>{type_html}</td>"
                f"<td>{open_badge}</td>"
                f"<td style='text-align:center'>{sc_html}</td>"
                f"<td>{xml_badge}</td>"
                f"<td>{res_badge}</td>"
                f"<td style='max-width:260px'>{err_html}</td>"
                f"</tr>"
            )

        sm_table = (
            "<table class='sm-tbl'>"
            "<thead><tr>"
            "<th>#</th><th>URL</th><th>Type</th><th>Accessible</th>"
            "<th>HTTP Status</th><th>XML / Structure</th><th>Result</th><th>Error Details</th>"
            "</tr></thead>"
            f"<tbody>{sm_rows_html}</tbody></table>"
        )

        sm_summary_cls  = "sm-summary-ok" if sm_overall == "PASS" else "sm-summary-fail"
        sm_summary_html = f"<div class='sm-summary {sm_summary_cls}'>{_esc(sm_summary)}</div>"

        sm_section_body = f"""
<div class="sm-chips">
  <div class="chip"><div class="chip-lbl">Total URLs</div><div class="chip-val">{sm_total}</div></div>
  <div class="chip"><div class="chip-lbl">Passed</div><div class="chip-val" style="color:#28a745">{sm_passed}</div></div>
  <div class="chip"><div class="chip-lbl">Failed</div><div class="chip-val" style="color:#dc3545">{sm_failed}</div></div>
  <div class="chip"><div class="chip-lbl">Sitemaps OK</div><div class="chip-val">{"&#10003; Yes" if sm_sit_ok else "&#10007; No"}</div></div>
  <div class="chip"><div class="chip-lbl">RSS Feeds OK</div><div class="chip-val">{"&#10003; Yes" if sm_rss_ok else "&#10007; No"}</div></div>
</div>
{sm_table}
{sm_summary_html}
"""

    # ── Unified AMP Page Validation section ──────────────────────────────────
    _amp_pages = [
        ("Bollywood Article",  amp_ran,       amp_url_val,       amp_page_open,       amp_can_result,   amp_err_status,   amp_ga_result,       amp_overall),
        ("Photo Story",        ps_amp_ran,    ps_amp_url_val,    ps_amp_page_open,    ps_amp_can_result, ps_amp_err_status, ps_amp_ga_result,   ps_amp_overall),
        ("BT Picks",           bt_amp_ran,    bt_amp_url_val,    bt_amp_page_open,    bt_amp_can_result, bt_amp_err_status, bt_amp_ga_result,   bt_amp_overall),
        ("Intimate Diaries",   id_amp_ran,    id_amp_url_val,    id_amp_page_open,    id_amp_can_result, id_amp_err_status, id_amp_ga_result,   id_amp_overall),
        ("Festival",           fest_amp_ran,  fest_amp_url_val,  fest_amp_page_open,  fest_amp_can_result, fest_amp_err_status, fest_amp_ga_result, fest_amp_overall),
        ("Astro Trends",       astro_amp_ran, astro_amp_url_val, astro_amp_page_open, astro_amp_can_result, astro_amp_err_status, astro_amp_ga_result, astro_amp_overall),
    ]
    _ran_amp_pages = [p for p in _amp_pages if p[1]]
    _all_amp_pass  = all(p[7] == "PASS" for p in _ran_amp_pages) if _ran_amp_pages else False
    unified_amp_overall       = "PASS" if _ran_amp_pages and _all_amp_pass else ("FAIL" if _ran_amp_pages else None)
    unified_amp_overall_badge = _amp_badge(unified_amp_overall)

    unified_amp_rows = ""
    for i, (page_type, ran, amp_url_v, page_open, canonical, amp_err, ga_v, overall) in enumerate(_amp_pages, 1):
        if not ran:
            unified_amp_rows += (
                f"<tr class='trow'>"
                f"<td class='td-num'>{i}</td>"
                f"<td class='td-name'>{_esc(page_type)}</td>"
                f"<td colspan='6' style='color:#adb5bd;font-size:11px;font-style:italic'>Not executed in this run</td>"
                f"</tr>"
            )
            continue
        open_badge = _amp_badge("PASS" if page_open else "FAIL")
        can_badge  = _amp_badge(canonical)
        err_badge  = _amp_badge(amp_err)
        ga_badge_v = _amp_badge(ga_v)
        ov_badge   = _amp_badge(overall)
        row_cls    = "trow-passed" if overall == "PASS" else "trow-failed"
        unified_amp_rows += (
            f"<tr class='trow {row_cls}'>"
            f"<td class='td-num'>{i}</td>"
            f"<td class='td-name'>{_esc(page_type)}</td>"
            f"<td style='font-family:\"Courier New\",monospace;font-size:10px;word-break:break-all;max-width:200px;color:#0d6efd'>{_esc(amp_url_v)}</td>"
            f"<td style='text-align:center'>{open_badge}</td>"
            f"<td style='text-align:center'>{can_badge}</td>"
            f"<td style='text-align:center'>{err_badge}</td>"
            f"<td style='text-align:center'>{ga_badge_v}</td>"
            f"<td style='text-align:center'>{ov_badge}</td>"
            f"</tr>"
        )

    unified_amp_section_body = (
        "<table class='res-tbl' style='font-size:12px'>"
        "<thead><tr>"
        "<th>#</th><th>Page Type</th><th>AMP URL</th>"
        "<th>Page Open</th><th>Canonical</th><th>AMP Check</th><th>GA</th><th>Overall</th>"
        "</tr></thead>"
        f"<tbody>{unified_amp_rows}</tbody></table>"
    )

    # ── Test result rows ──────────────────────────────────────────────────────
    rows_html = ""
    for i, t in enumerate(tests):
        oc = t["outcome"]
        friendly = t["name"].replace("test_", "").replace("_", " ").title()
        badge = f"<span class='badge b-{oc}'>{oc.upper()}</span>"

        err_preview = ""
        if t["error"]:
            last = t["error"].strip().splitlines()[-1][:120]
            err_preview = f"<span class='err-prev'>{_esc(last)}</span>"

        # Build expandable detail
        parts = []
        if t["logs"]:
            parts.append(
                f"<div class='dsec'>"
                f"<div class='dlbl'>📋 Captured Logs</div>"
                f"<pre class='log-blk'>{_esc(t['logs'])}</pre>"
                f"</div>"
            )
        if t["error"]:
            parts.append(
                f"<div class='dsec'>"
                f"<div class='dlbl'>❌ Error Details</div>"
                f"<pre class='err-blk'>{_esc(t['error'])}</pre>"
                f"</div>"
            )
        if t["screenshot_b64"]:
            parts.append(
                f"<div class='dsec'>"
                f"<div class='dlbl'>📸 Screenshot (on failure)</div>"
                f"<img src='data:image/png;base64,{t['screenshot_b64']}' class='ss-img'>"
                f"</div>"
            )

        detail_id = f"d{i}"
        expand_icon = "▼" if parts else ""

        rows_html += (
            f"<tr class='trow trow-{oc}' onclick=\"toggle('{detail_id}')\">"
            f"<td class='td-num'>{i + 1}</td>"
            f"<td class='td-name'>{_esc(friendly)}</td>"
            f"<td>{badge}</td>"
            f"<td class='td-dur'>{t['duration']}s</td>"
            f"<td class='td-ts'>{t['timestamp']}</td>"
            f"<td class='td-err'>{err_preview}</td>"
            f"<td class='td-exp'>{expand_icon}</td>"
            f"</tr>"
        )
        if parts:
            rows_html += (
                f"<tr class='drow' id='{detail_id}'>"
                f"<td colspan='7' class='dtd'>{''.join(parts)}</td>"
                f"</tr>"
            )

    # ── Assemble full HTML ────────────────────────────────────────────────────
    pill_cls  = "pill-ok"  if run_ok else "pill-fail"
    pill_text = "✓ ALL TESTS PASSED" if run_ok else f"✗ {failed} TEST(S) FAILED"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BombayTimes – Test Report</title>
<style>{css}</style>
</head>
<body>

<!-- ░░ HEADER ░░ -->
<div class="hdr">
  <div class="hdr-left">
    <span class="run-pill {pill_cls}">{pill_text}</span>
    <h1>BombayTimes – Playwright Test Report</h1>
    <p>Automated UI &amp; Network Validation Suite</p>
  </div>
  <div class="hdr-right">
    <div>▶ Started &nbsp;&nbsp;{start_str}</div>
    <div>■ Finished &nbsp;{end_str}</div>
    <div style="color:#ced4da">Duration: {duration}s</div>
  </div>
</div>

<!-- ░░ SUMMARY CARDS ░░ -->
<div class="cards">
  <div class="card c-tot"><div class="cv">{total}</div><div class="cl">Total</div></div>
  <div class="card c-pas"><div class="cv">{passed}</div><div class="cl">Passed</div></div>
  <div class="card c-fai"><div class="cv">{failed}</div><div class="cl">Failed</div></div>
  <div class="card c-ski"><div class="cv">{skipped}</div><div class="cl">Skipped</div></div>
  <div class="card c-rat"><div class="cv">{pass_rate}%</div><div class="cl">Pass Rate</div></div>
  <div class="card c-dur"><div class="cv">{duration}s</div><div class="cl">Duration</div></div>
</div>

<!-- ░░ PROGRESS BAR ░░ -->
<div class="prog-wrap">
  <div class="prog-lbl">{passed} of {total} tests passed ({pass_rate}%)</div>
  <div class="prog-bar"><div class="prog-fill" style="width:{pass_rate}%"></div></div>
</div>

<!-- ░░ ENVIRONMENT ░░ -->
<div class="sec">
  <div class="sec-title">⚙️ Environment Details</div>
  <table class="env-tbl">{env_rows}</table>
</div>

<!-- ░░ PAGE-LEVEL CANONICAL & GA VALIDATION ░░ -->
<div class="sec">
  <div class="sec-title">
    <span>&#128193; Page-Level Canonical &amp; GA Validation</span>
    <span style="font-size:12px;font-weight:400;color:#6c757d">{cat_total} page(s) checked &nbsp;&#183;&nbsp; &#9660; click row for screenshot</span>
  </div>
  <div class="ga-chips">
    <div class="chip"><div class="chip-lbl">Total Pages</div><div class="chip-val">{cat_total}</div></div>
    <div class="chip"><div class="chip-lbl">Canonical PASS</div><div class="chip-val" style="color:#28a745">{cat_can_pass}</div></div>
    <div class="chip"><div class="chip-lbl">Canonical FAIL</div><div class="chip-val" style="color:#dc3545">{cat_can_fail}</div></div>
    <div class="chip"><div class="chip-lbl">GA PASS</div><div class="chip-val" style="color:#28a745">{cat_ga_pass}</div></div>
    <div class="chip"><div class="chip-lbl">GA FAIL</div><div class="chip-val" style="color:#dc3545">{cat_ga_fail}</div></div>
  </div>
  {cat_section_body}
</div>

<!-- ░░ AMP PAGE VALIDATION ░░ -->
<div class="sec">
  <div class="sec-title">
    <span>&#9889; AMP Page Validation</span>
    {unified_amp_overall_badge}
  </div>
  {unified_amp_section_body}
</div>

<!-- ░░ SITEMAP AND RSS FEED VALIDATION ░░ -->
<div class="sec">
  <div class="sec-title">
    <span>&#128506; Sitemap and RSS Feed Validation</span>
    {sm_overall_badge}
  </div>
  {sm_section_body}
</div>

<!-- ░░ TEST RESULTS ░░ -->
<div class="sec">
  <div class="sec-title">
    <span>📋 Test Results ({total} tests)</span>
    <span style="font-size:12px;font-weight:400;color:#6c757d">▼ Click any row to expand logs &amp; details</span>
  </div>
  <table class="res-tbl">
    <thead>
      <tr>
        <th>#</th>
        <th>Test Case</th>
        <th>Status</th>
        <th>Duration</th>
        <th>Timestamp</th>
        <th>Error Summary</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>

<!-- ░░ FOOTER ░░ -->
<div class="footer">
  Generated by BombayTimes Playwright Suite &nbsp;·&nbsp;
  {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} &nbsp;·&nbsp;
  pytest {pytest.__version__} &nbsp;·&nbsp; Python {sys.version.split()[0]}
</div>

<script>{js}</script>
</body>
</html>"""

    out = pathlib.Path("reports") / "bt_report.html"
    out.write_text(html, encoding="utf-8")
    try:
        print(f"\n  Custom HTML report: {out.resolve()}")
    except UnicodeEncodeError:
        print(f"\n  Custom HTML report: {str(out.resolve()).encode('ascii', errors='replace').decode()}")
