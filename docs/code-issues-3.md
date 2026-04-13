# 3 Issues in the Test Code (and How to Fix Them)

Below are three common problems in the snippet, why each one is a problem, and how to fix it in a clean Playwright + pytest style.

---

## 1) Playwright lifecycle is handled incorrectly

### Problem
The code uses `sync_playwright().start()` directly and never calls `p.stop()`.

### Why this is bad
- Can leak Playwright driver processes.
- May create flaky behavior in longer test runs / CI.

### Fix
Use a context manager so setup/teardown is automatic:

```python
from playwright.sync_api import sync_playwright

def test_search_functionality():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://example.com")
        # ... test steps ...
        browser.close()
```

> In this project, using fixtures in `tests/conftest.py` is even better.

---

## 2) `time.sleep(...)` is used instead of condition-based waits

### Problem
The code uses fixed sleeps (`sleep(2)`, `sleep(3)`).

### Why this is bad
- Flaky tests when the page is slower than expected.
- Slow tests when the page is already ready.

### Fix
Wait for actual UI conditions with Playwright expectations:

```python
from playwright.sync_api import expect

search_box = page.locator("#search")
expect(search_box).to_be_visible()
search_box.fill("playwright testing")

results = page.locator(".result-item")
expect(results.first).to_be_visible()
```

---

## 3) No real assertion on test outcome

### Problem
The code sets `results = page.locator(".result-item")` but does not assert anything.

### Why this is bad
- Test may pass even when functionality is broken.
- Gives false confidence.

### Fix
Add meaningful assertions:

```python
from playwright.sync_api import expect

results = page.locator(".result-item")
expect(results).to_have_count(1)  # example expectation
# or:
expect(results.first).to_contain_text("playwright")
```

---

## Extra note

The snippet imports Selenium:

```python
from selenium import webdriver
```

but does not use it. Prefer one framework per test (here: Playwright).

