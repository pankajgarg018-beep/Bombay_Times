# BombayTimes Playwright POM Test Framework

This repository demonstrates a Python Playwright automation framework using the Page Object Model (POM), Pytest, and explicit waits.

Prerequisites:
- Python 3.8+
- Git

Setup (create virtualenv, install deps, install browser binaries):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install
```

Run tests:

```bash
pytest
```

Notes:
- Tests use Playwright sync API and explicit waits. Adjust `conftest.py` to run headed (set headless=False) for debugging.
- Selectors are written to prefer ARIA roles with href fallbacks; update them if the site markup changes.
