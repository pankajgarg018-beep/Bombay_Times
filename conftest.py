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
_ga_store_key = pytest.StashKey()

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

    _write_report(
        tests=tests,
        passed=passed,
        failed=failed,
        skipped=skipped,
        duration=duration,
        start_time=start_time,
        end_time=end_time,
        ga=ga_data,
    )


# ── Custom HTML report generator ──────────────────────────────────────────────

def _write_report(tests, passed, failed, skipped, duration, start_time, end_time, ga):
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

<!-- ░░ GA VALIDATION ░░ -->
<div class="sec">
  <div class="sec-title">
    <span>📡 Google Analytics Validation</span>
    {ga_badge}
  </div>
  <div class="ga-chips">
    <div class="chip"><div class="chip-lbl">Homepage URL</div><div class="chip-val">{_esc(ga_url)}</div></div>
    <div class="chip"><div class="chip-lbl">Total GA Calls</div><div class="chip-val">{ga_total}</div></div>
    <div class="chip"><div class="chip-lbl">Validation Status</div><div class="chip-val">{_esc(ga_status_txt)}</div></div>
    <div class="chip"><div class="chip-lbl">Keywords Matched</div><div class="chip-val">google-analytics · googletagmanager · gtag · collect</div></div>
  </div>
  <div class="sub-lbl">Captured GA Network Requests</div>
  {ga_calls_html}
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
