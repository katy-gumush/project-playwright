# ReadMeAIBugs — Bug handling exercise (static code review)

**Context:** AI-generated test code for a search scenario. **Do not run it** — the goal is a **static review**: identify at least **three** bugs/issues, explain **why** they matter, and suggest **fixes** (corrected code).

---

## Code under review

```python
from playwright.sync_api import sync_playwright
from selenium import webdriver
import time

def test_search_functionality():
    browser = sync_playwright().start().chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com")

    time.sleep(2)

    search_box = page.locator("#search")
    search_box.fill("playwright testing")

    page.locator(".button").click()

    time.sleep(3)

    results = page.locator(".result-item")

    browser.close()
```

---

## Bug 1 — Incorrect Playwright lifecycle

**What is wrong:**  
`sync_playwright().start()` is used without a `with` block and without `stop()`. Only `browser.close()` runs, so the Playwright driver instance may stay alive → **resource leaks** and flaky behavior in longer suites.

**Suggested fix:**

```python
from playwright.sync_api import sync_playwright

def test_search_functionality():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://example.com")
        # ... remaining steps ...
        browser.close()
```

(Alternatively: **pytest fixtures** + Playwright, as in this repo’s `conftest.py`.)

---

## Bug 2 — `time.sleep` instead of condition-based waits

**What is wrong:**  
`time.sleep(2)` and `time.sleep(3)` wait a fixed duration. If the page is slow, the test can fail; if it is fast, time is wasted. Playwright already auto-waits; prefer **`expect`** or waiting for a concrete state.

**Suggested fix:**

```python
from playwright.sync_api import expect

search_box = page.locator("#search")
expect(search_box).to_be_visible()
search_box.fill("playwright testing")

page.locator(".button").click()

results = page.locator(".result-item")
expect(results.first).to_be_visible()
```

---

## Bug 3 — No assertion — not a real test

**What is wrong:**  
`results = page.locator(".result-item")` is created but **nothing is verified** before `browser.close()`. The “test” can appear to succeed even when search is broken or there are no results.

**Suggested fix:**

```python
from playwright.sync_api import expect

results = page.locator(".result-item")
expect(results).to_have_count(1)  # or at least one, depending on requirements
# or:
expect(results.first).to_contain_text("playwright")
```

---

## Additional issue (4) — Unused Selenium import

**What is wrong:**  
`from selenium import webdriver` is never used. The script uses Playwright only — the import adds noise and confusion (and might imply Selenium is required).

**Suggested fix:** Remove the line `from selenium import webdriver`.

---

## Additional issue (5) — URL does not match the selectors

**What is wrong:**  
`https://example.com` typically has **no** `#search`, `.button`, or `.result-item` as assumed. The test is likely to fail for **environment/DOM** reasons even if the control flow were perfect.

**Suggested fix:** Point to a **URL** (or local HTML) where those elements actually exist, and align selectors with the real DOM.

---

## Summary

| # | Topic | Type |
|---|--------|------|
| 1 | `sync_playwright` without `with` / `stop` | Resource leak |
| 2 | `time.sleep` | Slow / timing-sensitive |
| 3 | Missing `assert` / `expect` on results | Meaningless test |
| 4 | Unused Selenium import | Noise / confusion |
| 5 | `example.com` vs. selectors | Environment mismatch |

---

*Exercise based on NESS-style “Bug Handling” material — static review only, no execution.*
