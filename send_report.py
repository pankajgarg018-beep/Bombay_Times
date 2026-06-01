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
def _build_email(s: dict) -> MIMEMultipart:
    exec_ok    = s["failed"] == "0"
    now_str    = datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
    subject    = f"Bombay Times Automation Report - {now_str}"

    amp_line = (
        f"{s['amp_pass']}/{s['amp_total']} page(s) passed"
        + (f" &nbsp;|&nbsp; <span style='color:#dc3545;font-weight:700'>{s['amp_fail']} Failed</span>" if s["amp_fail"] else "")
        if s["amp_total"] > 0 else "Not executed in this run"
    )
    sm_line = (
        f"{s['sm_passed']}/{s['sm_total']} URL(s) passed"
        + (f" &nbsp;|&nbsp; <span style='color:#dc3545;font-weight:700'>{s['sm_failed']} Failed</span>" if s["sm_failed"] != "0" else "")
        if s["sm_total"] != "?" else "Not executed in this run"
    )

    status_color = "#28a745" if exec_ok else "#dc3545"
    status_bg    = "#d4edda" if exec_ok else "#f8d7da"
    status_label = "ALL TESTS PASSED" if exec_ok else f"{s['failed']} TEST(S) FAILED"
    status_icon  = "&#10003;" if exec_ok else "&#10007;"

    # ── Plain-text fallback ───────────────────────────────────────────────────
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
        "Regards,\nAutomation System | BombayTimes QA\n"
    )

    # ── HTML body ─────────────────────────────────────────────────────────────
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Segoe UI',Arial,sans-serif;font-size:14px;color:#333;">

<!-- Wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f0f2f5;padding:30px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;">

  <!-- ░░ HEADER ░░ -->
  <tr>
    <td style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 55%,#0f3460 100%);
               border-radius:12px 12px 0 0;padding:28px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td>
            <div style="display:inline-block;background:{status_color};color:#fff;
                        padding:5px 16px;border-radius:20px;font-size:12px;
                        font-weight:700;letter-spacing:.5px;margin-bottom:10px;">
              {status_icon}&nbsp; {status_label}
            </div>
            <div style="color:#fff;font-size:20px;font-weight:700;margin-bottom:4px;">
              BombayTimes &mdash; Automation Report
            </div>
            <div style="color:#9fa8b5;font-size:12px;">
              Playwright UI &amp; Network Validation Suite
            </div>
          </td>
          <td align="right" valign="top">
            <div style="color:#9fa8b5;font-size:11px;line-height:2;text-align:right;">
              <div>Generated: <strong style="color:#ced4da;">{now_str}</strong></div>
              <div>Started &nbsp;: <strong style="color:#ced4da;">{s['started']}</strong></div>
              <div>Finished : <strong style="color:#ced4da;">{s['finished']}</strong></div>
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ░░ GREETING ░░ -->
  <tr>
    <td style="background:#fff;padding:24px 32px 8px 32px;">
      <p style="margin:0 0 6px 0;font-size:15px;font-weight:600;color:#343a40;">Hello,</p>
      <p style="margin:0;font-size:13px;color:#555;line-height:1.6;">
        Please find attached the latest <strong>BombayTimes Automation Execution Report</strong>.
        The report contains detailed results for all UI, canonical, GA, AMP, and Sitemap/RSS validations
        executed in this run.
      </p>
    </td>
  </tr>

  <!-- ░░ STATUS BANNER ░░ -->
  <tr>
    <td style="background:#fff;padding:20px 32px 0 32px;">
      <table width="100%" cellpadding="16" cellspacing="0" border="0"
             style="background:{status_bg};border:1px solid {status_color};
                    border-radius:8px;border-left:5px solid {status_color};">
        <tr>
          <td>
            <span style="font-size:22px;font-weight:800;color:{status_color};">
              {status_icon}&nbsp; {status_label}
            </span>
            <div style="margin-top:4px;font-size:12px;color:#555;">
              Pass Rate: <strong>{s['pass_rate']}</strong> &nbsp;&bull;&nbsp;
              Duration: <strong>{s['duration']}</strong>
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ░░ SUMMARY CARDS ░░ -->
  <tr>
    <td style="background:#fff;padding:20px 32px 0 32px;">
      <div style="font-size:13px;font-weight:700;color:#343a40;
                  text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;">
        Test Execution Summary
      </div>
      <table width="100%" cellpadding="0" cellspacing="8" border="0">
        <tr>
          <td width="25%" style="padding:4px;">
            <table width="100%" cellpadding="14" cellspacing="0" border="0"
                   style="background:#f8f9fa;border-radius:8px;border-top:3px solid #495057;text-align:center;">
              <tr><td>
                <div style="font-size:26px;font-weight:800;color:#495057;">{s['total']}</div>
                <div style="font-size:10px;color:#6c757d;text-transform:uppercase;
                             letter-spacing:.6px;margin-top:4px;">Total Tests</div>
              </td></tr>
            </table>
          </td>
          <td width="25%" style="padding:4px;">
            <table width="100%" cellpadding="14" cellspacing="0" border="0"
                   style="background:#f8f9fa;border-radius:8px;border-top:3px solid #28a745;text-align:center;">
              <tr><td>
                <div style="font-size:26px;font-weight:800;color:#28a745;">{s['passed']}</div>
                <div style="font-size:10px;color:#6c757d;text-transform:uppercase;
                             letter-spacing:.6px;margin-top:4px;">Passed</div>
              </td></tr>
            </table>
          </td>
          <td width="25%" style="padding:4px;">
            <table width="100%" cellpadding="14" cellspacing="0" border="0"
                   style="background:#f8f9fa;border-radius:8px;border-top:3px solid #dc3545;text-align:center;">
              <tr><td>
                <div style="font-size:26px;font-weight:800;color:#dc3545;">{s['failed']}</div>
                <div style="font-size:10px;color:#6c757d;text-transform:uppercase;
                             letter-spacing:.6px;margin-top:4px;">Failed</div>
              </td></tr>
            </table>
          </td>
          <td width="25%" style="padding:4px;">
            <table width="100%" cellpadding="14" cellspacing="0" border="0"
                   style="background:#f8f9fa;border-radius:8px;border-top:3px solid #0d6efd;text-align:center;">
              <tr><td>
                <div style="font-size:26px;font-weight:800;color:#0d6efd;">{s['pass_rate']}</div>
                <div style="font-size:10px;color:#6c757d;text-transform:uppercase;
                             letter-spacing:.6px;margin-top:4px;">Pass Rate</div>
              </td></tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ░░ AMP VALIDATION ░░ -->
  <tr>
    <td style="background:#fff;padding:20px 32px 0 32px;">
      <table width="100%" cellpadding="14" cellspacing="0" border="0"
             style="background:#f8f9fa;border-radius:8px;border-left:4px solid #6f42c1;">
        <tr>
          <td>
            <div style="font-size:13px;font-weight:700;color:#343a40;margin-bottom:6px;">
              &#9889; AMP Page Validation
            </div>
            <div style="font-size:13px;color:#555;">
              {amp_line}
            </div>
          </td>
          <td align="right" valign="middle" width="90">
            <span style="display:inline-block;padding:5px 14px;border-radius:20px;font-size:12px;
                         font-weight:700;background:{'#d4edda' if not s['amp_fail'] else '#f8d7da'};
                         color:{'#155724' if not s['amp_fail'] else '#721c24'};">
              {'&#10003; PASS' if not s['amp_fail'] else '&#10007; FAIL'}
            </span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ░░ SITEMAP / RSS ░░ -->
  <tr>
    <td style="background:#fff;padding:12px 32px 0 32px;">
      <table width="100%" cellpadding="14" cellspacing="0" border="0"
             style="background:#f8f9fa;border-radius:8px;border-left:4px solid #20c997;">
        <tr>
          <td>
            <div style="font-size:13px;font-weight:700;color:#343a40;margin-bottom:6px;">
              &#128506; Sitemap &amp; RSS Feed Validation
            </div>
            <div style="font-size:13px;color:#555;">
              {sm_line}
            </div>
          </td>
          <td align="right" valign="middle" width="90">
            <span style="display:inline-block;padding:5px 14px;border-radius:20px;font-size:12px;
                         font-weight:700;background:{'#d4edda' if s['sm_failed'] == '0' else '#f8d7da'};
                         color:{'#155724' if s['sm_failed'] == '0' else '#721c24'};">
              {'&#10003; PASS' if s['sm_failed'] == '0' else '&#10007; FAIL'}
            </span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ░░ ATTACHMENT NOTE ░░ -->
  <tr>
    <td style="background:#fff;padding:20px 32px 0 32px;">
      <table width="100%" cellpadding="12" cellspacing="0" border="0"
             style="background:#e8f4fd;border-radius:8px;border:1px solid #b8daff;">
        <tr>
          <td>
            <span style="font-size:20px;">&#128206;</span>
            <span style="font-size:13px;color:#004085;font-weight:600;margin-left:8px;">
              Full Detailed Report Attached
            </span>
            <div style="font-size:12px;color:#555;margin-top:4px;margin-left:30px;">
              Open the attached <strong>bt_report.html</strong> file in any browser
              to view the complete test report with logs, screenshots, and detailed validation results.
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ░░ REGARDS ░░ -->
  <tr>
    <td style="background:#fff;padding:24px 32px 28px 32px;">
      <p style="margin:0;font-size:13px;color:#555;line-height:1.8;">
        Regards,<br>
        <strong style="color:#343a40;font-size:14px;">Automation System</strong><br>
        <span style="color:#6c757d;font-size:12px;">BombayTimes QA &bull; Playwright Automation Suite</span>
      </p>
    </td>
  </tr>

  <!-- ░░ FOOTER ░░ -->
  <tr>
    <td style="background:linear-gradient(135deg,#1a1a2e,#0f3460);
               border-radius:0 0 12px 12px;padding:16px 32px;text-align:center;">
      <span style="color:#9fa8b5;font-size:11px;">
        BombayTimes Playwright Automation Suite &nbsp;&bull;&nbsp;
        Generated on {now_str}
      </span>
    </td>
  </tr>

</table>
</td></tr>
</table>

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

    if REPORT_PATH.exists():
        with open(REPORT_PATH, "rb") as fh:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(fh.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{REPORT_PATH.name}"',
        )
        msg_outer.attach(part)
        print(f"  Attaching: {REPORT_PATH.name}  ({REPORT_PATH.stat().st_size:,} bytes)")
    else:
        print(f"  WARNING: Report file not found at {REPORT_PATH}")

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

    msg = _build_email(s)

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
