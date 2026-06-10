"""
Standalone script to send the latest BombayTimes automation report via email.
Run this independently — does NOT execute any test cases.

Usage:
    python send_report.py

Configure your Gmail App Password below (or via environment variables):
    EMAIL_PASSWORD  →  your 16-character Gmail App Password
"""

import os
import pathlib
import re
import smtplib
import ssl
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email                import encoders

# ── Configuration ─────────────────────────────────────────────────────────────
SMTP_HOST  = "smtp.gmail.com"
SMTP_PORT  = 587
USE_TLS    = True
FROM_ADDR  = os.environ.get("EMAIL_FROM",     "pankajgarg018@gmail.com")
USERNAME   = os.environ.get("EMAIL_USER",     "pankajgarg018@gmail.com")
PASSWORD   = os.environ.get("EMAIL_PASSWORD", "")   # ← paste your 16-char App Password here
TO_ADDRS   = ["Pankaj.garg1@timesofindia.com"]
REPORT_PATH = pathlib.Path("reports") / "bt_report.html"


# ── PDF generator ─────────────────────────────────────────────────────────────
def _find_chromium_exe() -> str:
    """Return Chrome/Chromium executable — mirrors test-suite browser discovery."""
    candidates = [
        os.environ.get("CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Chromium\Application\chrome.exe",
        str(pathlib.Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe"),
    ]
    for c in candidates:
        if c and pathlib.Path(c).exists():
            return c
    # ms-playwright fallback
    pw_dir = pathlib.Path.home() / "AppData" / "Local" / "ms-playwright"
    if pw_dir.exists():
        for item in pw_dir.iterdir():
            if item.is_dir() and item.name.startswith("chromium-"):
                for sub in ("chrome-win64", "chrome-win"):
                    exe = item / sub / "chrome.exe"
                    if exe.exists():
                        return str(exe)
    return None


def _generate_pdf() -> pathlib.Path:
    """Convert reports/bt_report.html to reports/bt_report.pdf using Playwright.

    Uses the existing Chromium installation (avoids headless-shell download).
    Returns the PDF path on success, None on failure.
    """
    from playwright.sync_api import sync_playwright

    pdf_path = REPORT_PATH.with_suffix(".pdf")
    try:
        print("\n  [PDF] Generating PDF from HTML report ...")
        file_uri   = REPORT_PATH.resolve().as_uri()
        chrome_exe = _find_chromium_exe()

        launch_kwargs = dict(
            headless=False,
            args=["--window-position=-10000,-10000", "--window-size=1,1",
                  "--no-first-run", "--no-default-browser-check",
                  "--disable-extensions"],
        )
        if chrome_exe:
            launch_kwargs["executable_path"] = chrome_exe
            print(f"  [PDF] Using Chrome: {chrome_exe}")

        with sync_playwright() as _pw:
            browser = _pw.chromium.launch(**launch_kwargs)
            ctx     = browser.new_context()
            pg      = ctx.new_page()
            pg.goto(file_uri, wait_until="load", timeout=30000)
            pg.wait_for_timeout(1500)

            # Inject print-fix CSS to prevent blank trailing pages in PDF
            pg.evaluate("""
                () => {
                    const s = document.createElement('style');
                    s.textContent = [
                        'html, body { height: auto !important; overflow: visible !important; }',
                        '.drow { display: none !important; }',
                        '.log-blk, .err-blk { max-height: none !important; overflow: visible !important; }',
                    ].join(' ');
                    document.head.appendChild(s);
                }
            """)

            pg.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={
                    "top":    "12mm",
                    "right":  "10mm",
                    "bottom": "12mm",
                    "left":   "10mm",
                },
            )
            browser.close()

        print(f"  [PDF] Generated: {pdf_path.name}  ({pdf_path.stat().st_size:,} bytes)")
        return pdf_path

    except Exception as exc:
        safe_msg = str(exc).encode("ascii", errors="replace").decode()
        print(f"\n  [PDF] PDF generation failed: {safe_msg}")
        return None


# ── HTML report parser ─────────────────────────────────────────────────────────
def _parse_report(path: pathlib.Path) -> dict:
    """Extract summary numbers from the HTML report without running tests."""
    content = path.read_text(encoding="utf-8")

    def _card(cls):
        m = re.search(rf'class="card {cls}"><div class="cv">([^<]+)<', content)
        return m.group(1).strip() if m else "?"

    total     = _card("c-tot")
    passed    = _card("c-pas")
    failed    = _card("c-fai")
    skipped   = _card("c-ski")
    duration  = _card("c-dur")
    pass_rate = _card("c-rat")

    m_start  = re.search(r'Started &nbsp;&nbsp;([^<]+)<', content)
    m_finish = re.search(r'Finished &nbsp;([^<]+)<', content)
    started  = m_start.group(1).strip()  if m_start  else "?"
    finished = m_finish.group(1).strip() if m_finish else "?"

    # AMP table — count PASS/FAIL rows in unified AMP section
    amp_section = re.search(
        r'AMP Page Validation(.*?)(?:Sitemap and RSS|TEST RESULTS)',
        content, re.S
    )
    amp_pass = amp_fail = 0
    if amp_section:
        seg = amp_section.group(1)
        amp_pass = seg.count("trow-passed")
        amp_fail = seg.count("trow-failed")
    amp_total = amp_pass + amp_fail

    # Sitemap chips
    sm_total_m  = re.search(r'Total URLs.*?chip-val">\s*(\d+)', content, re.S)
    sm_passed_m = re.search(r'Passed.*?color:#28a745">\s*(\d+)', content, re.S)
    sm_failed_m = re.search(r'Failed.*?color:#dc3545">\s*(\d+)', content, re.S)
    sm_total  = sm_total_m.group(1)  if sm_total_m  else "?"
    sm_passed = sm_passed_m.group(1) if sm_passed_m else "?"
    sm_failed = sm_failed_m.group(1) if sm_failed_m else "?"

    return {
        "total": total, "passed": passed, "failed": failed,
        "skipped": skipped, "duration": duration, "pass_rate": pass_rate,
        "started": started, "finished": finished,
        "amp_total": amp_total, "amp_pass": amp_pass, "amp_fail": amp_fail,
        "sm_total": sm_total, "sm_passed": sm_passed, "sm_failed": sm_failed,
    }


# ── Email builder ──────────────────────────────────────────────────────────────
def _build_email(s: dict, attach_path: pathlib.Path = None) -> MIMEMultipart:
    exec_ok      = s["failed"] == "0"
    now_str      = datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
    subject      = f"Bombay Times Automation Report - {now_str}"

    # Outlook-safe: plain text for amp_line / sm_line (no inline <span> in table cells)
    amp_line_txt = (
        f"{s['amp_pass']}/{s['amp_total']} page(s) passed"
        + (f", {s['amp_fail']} Failed" if s["amp_fail"] else "")
        if s["amp_total"] > 0 else "Not executed in this run"
    )
    sm_line_txt = (
        f"{s['sm_passed']}/{s['sm_total']} URL(s) passed"
        + (f", {s['sm_failed']} Failed" if s["sm_failed"] != "0" else "")
        if s["sm_total"] != "?" else "Not executed in this run"
    )

    status_color  = "#28a745" if exec_ok else "#dc3545"
    status_bg     = "#d4edda" if exec_ok else "#f8d7da"
    status_border = "#c3e6cb" if exec_ok else "#f5c6cb"
    status_label  = "ALL TESTS PASSED" if exec_ok else f"{s['failed']} TEST(S) FAILED"
    status_icon   = "&#10003;" if exec_ok else "&#10007;"

    amp_ok        = not s["amp_fail"]
    amp_pill_bg   = "#d4edda" if amp_ok else "#f8d7da"
    amp_pill_fg   = "#155724" if amp_ok else "#721c24"
    amp_pill_lbl  = "&#10003; PASS" if amp_ok else "&#10007; FAIL"

    sm_ok         = s["sm_failed"] == "0"
    sm_pill_bg    = "#d4edda" if sm_ok else "#f8d7da"
    sm_pill_fg    = "#155724" if sm_ok else "#721c24"
    sm_pill_lbl   = "&#10003; PASS" if sm_ok else "&#10007; FAIL"

    # ── Plain-text fallback ──────────────────────────────────────────────────
    plain_body = (
        "Hello,\n\n"
        "Please find attached the latest Bombay Times Automation Execution Report.\n\n"
        f"Execution Status    : {'PASS - All Tests Passed' if exec_ok else 'FAIL - ' + s['failed'] + ' Test(s) Failed'}\n"
        f"Execution Started   : {s['started']}\n"
        f"Execution Completed : {s['finished']}\n"
        f"Total Duration      : {s['duration']}\n"
        f"Pass Rate           : {s['pass_rate']}\n\n"
        "Test Results:\n"
        f"  Total Validations : {s['total']}\n"
        f"  Passed            : {s['passed']}\n"
        f"  Failed            : {s['failed']}\n"
        f"  Skipped           : {s['skipped']}\n\n"
        f"AMP Validation      : {s['amp_pass']}/{s['amp_total']} passed\n"
        f"Sitemap / RSS       : {s['sm_passed']}/{s['sm_total']} passed\n\n"
        "Please open the attached HTML file for the full detailed report.\n\n"
        "Regards,\n BombayTimes QA Team \n"
    )

    # ── HTML body (Outlook-safe: bgcolor attrs, no gradients, table borders) ──
    html_body = f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml"
      xmlns:v="urn:schemas-microsoft-com:vml"
      xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<!--[if gte mso 9]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->
<style>
  body,table,td{{font-family:'Segoe UI',Arial,sans-serif;font-size:14px;color:#333;margin:0;padding:0;}}
  img{{border:0;display:block;}}
  a{{color:#0d6efd;}}
</style>
</head>
<body style="margin:0;padding:0;background-color:#f0f2f5;">

<!-- ░░ OUTER WRAPPER ░░ -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f0f2f5"
       style="background-color:#f0f2f5;">
<tr><td align="center" style="padding:30px 16px;">

  <!-- ░░ MAIN CONTAINER ░░ -->
  <table width="620" cellpadding="0" cellspacing="0" border="0"
         style="width:620px;max-width:620px;">

    <!-- ░░ HEADER ░░ -->
    <tr>
      <td bgcolor="#16213e" style="background-color:#16213e;padding:0;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <!-- coloured top bar -->
            <td colspan="2" bgcolor="{status_color}"
                style="background-color:{status_color};height:5px;line-height:5px;font-size:1px;">&nbsp;</td>
          </tr>
          <tr>
            <td style="padding:24px 28px 20px 28px;" valign="top">
              <!-- status pill -->
              <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;">
                <tr>
                  <td bgcolor="{status_color}" style="background-color:{status_color};
                      padding:5px 16px;border-radius:20px;">
                    <span style="color:#ffffff;font-size:12px;font-weight:700;
                                 letter-spacing:.5px;">
                      {status_icon}&nbsp; {status_label}
                    </span>
                  </td>
                </tr>
              </table>
              <div style="color:#ffffff;font-size:20px;font-weight:700;
                          margin-bottom:4px;line-height:1.3;">
                BombayTimes &mdash; Testing Report
              </div>
        
            </td>
            <td style="padding:24px 28px 20px 0;" valign="top" align="right" width="190">
              <table cellpadding="0" cellspacing="0" border="0" align="right">
                <tr><td style="color:#9fa8b5;font-size:11px;line-height:1.9;
                               text-align:right;white-space:nowrap;">
                  Generated:<br>
                  <strong style="color:#ced4da;">{now_str}</strong><br>
                  Started:<br>
                  <strong style="color:#ced4da;">{s['started']}</strong><br>
                  Finished:<br>
                  <strong style="color:#ced4da;">{s['finished']}</strong>
                </td></tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ░░ WHITE BODY ░░ -->
    <tr>
      <td bgcolor="#ffffff" style="background-color:#ffffff;">

        <!-- GREETING -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:24px 28px 10px 28px;">
              <p style="margin:0 0 8px 0;font-size:15px;font-weight:600;
                        color:#343a40;">Hello,</p>
              <p style="margin:0;font-size:13px;color:#555;line-height:1.7;">
                Please find attached the latest
                <strong>BombayTimes Automation Execution Report</strong>.
                The report contains detailed results for all UI, Canonical, GA,
                AMP, and Sitemap / RSS validations executed in this run.
              </p>
            </td>
          </tr>
        </table>

        <!-- STATUS BANNER -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:12px 28px 0 28px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <!-- left accent bar -->
                  <td width="5" bgcolor="{status_color}"
                      style="background-color:{status_color};border-radius:4px 0 0 4px;">
                  </td>
                  <td bgcolor="{status_bg}"
                      style="background-color:{status_bg};padding:14px 18px;
                             border:1px solid {status_border};border-left:none;">
                    <span style="font-size:18px;font-weight:800;color:{status_color};">
                      {status_icon}&nbsp; {status_label}
                    </span>
                    <br>
                    <span style="font-size:12px;color:#555;">
                      Pass Rate: <strong>{s['pass_rate']}</strong>
                      &nbsp;&bull;&nbsp;
                      Duration: <strong>{s['duration']}</strong>
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- SECTION TITLE: TEST RESULTS -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:22px 28px 10px 28px;">
              <span style="font-size:12px;font-weight:700;color:#343a40;
                           text-transform:uppercase;letter-spacing:.6px;">
                Test Execution Summary
              </span>
            </td>
          </tr>
        </table>

        <!-- SUMMARY CARDS (4 columns) -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:0 28px 0 28px;">
              <table width="100%" cellpadding="0" cellspacing="8" border="0">
                <tr valign="top">

                  <!-- Total -->
                  <td width="25%" style="padding:4px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td colspan="2" bgcolor="#495057"
                            style="background-color:#495057;height:4px;
                                   line-height:4px;font-size:1px;">&nbsp;</td>
                      </tr>
                      <tr>
                        <td bgcolor="#f8f9fa" style="background-color:#f8f9fa;
                            padding:14px 8px;text-align:center;">
                          <div style="font-size:28px;font-weight:800;color:#495057;
                                      line-height:1;">{s['total']}</div>
                          <div style="font-size:10px;color:#6c757d;
                                      text-transform:uppercase;letter-spacing:.5px;
                                      margin-top:5px;">Total Tests</div>
                        </td>
                      </tr>
                    </table>
                  </td>

                  <!-- Passed -->
                  <td width="25%" style="padding:4px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td bgcolor="#28a745"
                            style="background-color:#28a745;height:4px;
                                   line-height:4px;font-size:1px;">&nbsp;</td>
                      </tr>
                      <tr>
                        <td bgcolor="#f8f9fa" style="background-color:#f8f9fa;
                            padding:14px 8px;text-align:center;">
                          <div style="font-size:28px;font-weight:800;color:#28a745;
                                      line-height:1;">{s['passed']}</div>
                          <div style="font-size:10px;color:#6c757d;
                                      text-transform:uppercase;letter-spacing:.5px;
                                      margin-top:5px;">Passed</div>
                        </td>
                      </tr>
                    </table>
                  </td>

                  <!-- Failed -->
                  <td width="25%" style="padding:4px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td bgcolor="#dc3545"
                            style="background-color:#dc3545;height:4px;
                                   line-height:4px;font-size:1px;">&nbsp;</td>
                      </tr>
                      <tr>
                        <td bgcolor="#f8f9fa" style="background-color:#f8f9fa;
                            padding:14px 8px;text-align:center;">
                          <div style="font-size:28px;font-weight:800;color:#dc3545;
                                      line-height:1;">{s['failed']}</div>
                          <div style="font-size:10px;color:#6c757d;
                                      text-transform:uppercase;letter-spacing:.5px;
                                      margin-top:5px;">Failed</div>
                        </td>
                      </tr>
                    </table>
                  </td>

                  <!-- Pass Rate -->
                  <td width="25%" style="padding:4px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td bgcolor="#0d6efd"
                            style="background-color:#0d6efd;height:4px;
                                   line-height:4px;font-size:1px;">&nbsp;</td>
                      </tr>
                      <tr>
                        <td bgcolor="#f8f9fa" style="background-color:#f8f9fa;
                            padding:14px 8px;text-align:center;">
                          <div style="font-size:22px;font-weight:800;color:#0d6efd;
                                      line-height:1;">{s['pass_rate']}</div>
                          <div style="font-size:10px;color:#6c757d;
                                      text-transform:uppercase;letter-spacing:.5px;
                                      margin-top:5px;">Pass Rate</div>
                        </td>
                      </tr>
                    </table>
                  </td>

                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- AMP VALIDATION ROW -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:16px 28px 0 28px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr valign="middle">
                  <!-- purple accent -->
                  <td width="5" bgcolor="#6f42c1"
                      style="background-color:#6f42c1;">
                  </td>
                  <td bgcolor="#f3f0ff"
                      style="background-color:#f3f0ff;padding:14px 16px;
                             border:1px solid #d6ccf5;border-left:none;">
                    <span style="font-size:13px;font-weight:700;color:#343a40;">
                      &#9889; AMP Page Validation
                    </span>
                    <br>
                    <span style="font-size:12px;color:#555;margin-top:3px;
                                 display:block;">{amp_line_txt}</span>
                  </td>
                  <td bgcolor="#f3f0ff"
                      style="background-color:#f3f0ff;padding:14px 16px;
                             border:1px solid #d6ccf5;border-left:none;
                             white-space:nowrap;" width="90" align="right">
                    <table cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td bgcolor="{amp_pill_bg}"
                            style="background-color:{amp_pill_bg};
                                   padding:5px 13px;border-radius:20px;">
                          <span style="font-size:11px;font-weight:700;
                                       color:{amp_pill_fg};">{amp_pill_lbl}</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- SITEMAP / RSS ROW -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:10px 28px 0 28px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr valign="middle">
                  <!-- teal accent -->
                  <td width="5" bgcolor="#20c997"
                      style="background-color:#20c997;">
                  </td>
                  <td bgcolor="#f0fdf9"
                      style="background-color:#f0fdf9;padding:14px 16px;
                             border:1px solid #c3f0e0;border-left:none;">
                    <span style="font-size:13px;font-weight:700;color:#343a40;">
                      &#128506; Sitemap &amp; RSS Feed Validation
                    </span>
                    <br>
                    <span style="font-size:12px;color:#555;margin-top:3px;
                                 display:block;">{sm_line_txt}</span>
                  </td>
                  <td bgcolor="#f0fdf9"
                      style="background-color:#f0fdf9;padding:14px 16px;
                             border:1px solid #c3f0e0;border-left:none;
                             white-space:nowrap;" width="90" align="right">
                    <table cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td bgcolor="{sm_pill_bg}"
                            style="background-color:{sm_pill_bg};
                                   padding:5px 13px;border-radius:20px;">
                          <span style="font-size:11px;font-weight:700;
                                       color:{sm_pill_fg};">{sm_pill_lbl}</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- ATTACHMENT NOTE -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:16px 28px 0 28px;">
              <table width="100%" cellpadding="14" cellspacing="0" border="0">
                <tr>
                  <td bgcolor="#e8f4fd"
                      style="background-color:#e8f4fd;border:1px solid #b8daff;
                             padding:14px 16px;">
                    <span style="font-size:18px;">&#128206;</span>
                    <span style="font-size:13px;color:#004085;font-weight:700;
                                 margin-left:6px;">Full Detailed Report Attached</span>
                    <br>
                    <span style="font-size:12px;color:#555;margin-left:26px;
                                 display:block;margin-top:4px;">
                      Open the attached <strong>bt_report.pdf</strong> file in any
                      browser to view complete test logs, AMP details,
                      and validation results.
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        <!-- REGARDS -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:24px 28px 28px 28px;">
              <p style="margin:0;font-size:13px;color:#555;line-height:1.9;">
                Regards,<br>
                <strong style="color:#343a40;font-size:14px;">B</strong><br>
               
              </p>
            </td>
          </tr>
        </table>

      </td><!-- end WHITE BODY -->
    </tr>

    <!-- ░░ FOOTER ░░ -->
    <tr>
      <td bgcolor="#16213e" style="background-color:#16213e;padding:16px 28px;
          text-align:center;">
        <!-- top accent line -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="margin-bottom:10px;">
          <tr>
            <td bgcolor="{status_color}"
                style="background-color:{status_color};height:2px;
                       line-height:2px;font-size:1px;">&nbsp;</td>
          </tr>
        </table>
        <span style="color:#9fa8b5;font-size:11px;">
          BombayTimes Testing Automation Report<br>
          &nbsp;&bull;&nbsp;
          Generated on {now_str}
        </span>
      </td>
    </tr>

  </table><!-- end MAIN CONTAINER -->

</td></tr>
</table><!-- end OUTER WRAPPER -->

</body>
</html>"""

    # ── Assemble MIME structure: mixed > alternative + attachment ─────────────
    msg_outer            = MIMEMultipart("mixed")
    msg_outer["From"]    = FROM_ADDR
    msg_outer["To"]      = ", ".join(TO_ADDRS)
    msg_outer["Subject"] = subject

    msg_alt = MIMEMultipart("alternative")
    msg_alt.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg_alt.attach(MIMEText(html_body,  "html",  "utf-8"))
    msg_outer.attach(msg_alt)

    # Attach PDF only (HTML is retained internally but not emailed)
    if attach_path and pathlib.Path(attach_path).exists():
        ap = pathlib.Path(attach_path)
        with open(ap, "rb") as fh:
            part = MIMEBase("application", "pdf")
            part.set_payload(fh.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{ap.name}"',
        )
        msg_outer.attach(part)
        print(f"  Attaching PDF: {ap.name}  ({ap.stat().st_size:,} bytes)")
    else:
        print("  WARNING: PDF report not available — sending email without attachment.")

    return msg_outer


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("\n== BombayTimes Report Email Sender ================================")

    if not REPORT_PATH.exists():
        print(f"ERROR: No report found at {REPORT_PATH.resolve()}")
        print("       Run the test suite first: python -m pytest")
        return

    password = PASSWORD or os.environ.get("EMAIL_PASSWORD", "")
    if not password:
        print(
            "\nERROR: Gmail App Password not set.\n"
            "  Option 1 — Set env var then re-run:\n"
            "    $env:EMAIL_PASSWORD = 'your-16-char-app-password'\n"
            "    python send_report.py\n"
            "  Option 2 — Edit PASSWORD = '...' directly in this file.\n\n"
            "How to get a Gmail App Password:\n"
            "  1. Go to  https://myaccount.google.com/security\n"
            "  2. Enable 2-Step Verification (if not already on)\n"
            "  3. Go to  https://myaccount.google.com/apppasswords\n"
            "  4. App name: 'BT Automation'  →  click Create\n"
            "  5. Copy the 16-character password shown\n"
        )
        return

    print(f"  Report  : {REPORT_PATH.resolve()}")
    print(f"  From    : {FROM_ADDR}")
    print(f"  To      : {', '.join(TO_ADDRS)}")

    s = _parse_report(REPORT_PATH)
    print(f"\n  Summary : {s['passed']}/{s['total']} passed  |  {s['failed']} failed  |  {s['duration']}")
    print(f"  Run     : {s['started']} -> {s['finished']}")

    # Generate PDF before building email
    pdf_path = _generate_pdf()
    msg = _build_email(s, attach_path=pdf_path)

    print(f"\n  Connecting to {SMTP_HOST}:{SMTP_PORT} (STARTTLS) …")
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(USERNAME, password)
        server.sendmail(FROM_ADDR, TO_ADDRS, msg.as_string())
        server.quit()
        print(f"  Email sent successfully to: {', '.join(TO_ADDRS)}")
    except smtplib.SMTPAuthenticationError:
        print(
            "\n  AUTH ERROR: Gmail rejected the password.\n"
            "  Make sure you used the 16-character App Password,\n"
            "  not your regular Gmail login password.\n"
            "  Also confirm 2-Step Verification is enabled on the account."
        )
    except Exception as exc:
        print(f"\n  Failed to send email: {exc}")

    print("===================================================================\n")


if __name__ == "__main__":
    main()
