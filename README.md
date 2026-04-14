# eBay E2E — Playwright / Python

End-to-end automation for an e-commerce flow on **[eBay.com](https://www.ebay.com/)** using **Playwright**, **pytest**, **Page Object Model**, and **data-driven** test cases from JSON.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | 3.12+ recommended |
| pip | Bundled with Python |
| Network access | To install packages and reach ebay.com |
| Allure CLI | Optional — only needed to open HTML reports locally |

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
python -m playwright install    # downloads Chromium (and others if you change BROWSER)
mkdir -p artifacts
```

### Credentials

The test signs in to eBay with a real account. Credentials are loaded from `data/ebay/credentials.json`, which is **gitignored** and never committed.

```bash
cp data/ebay/credentials.example.json data/ebay/credentials.json
# then edit data/ebay/credentials.json and fill in your username and password
```

```json
{
  "username": "your_ebay_username_or_email",
  "password": "your_ebay_password"
}
```

If the file is missing or either field is empty, sign-in cases fail immediately with a clear error message before opening the browser. Cases with `login_as_guest: true` in `cases.json` do not read this file.

---

## How to run

The browser is **headless by default**. eBay aggressively blocks headless browsers — run headed and use `PWDEBUG=1` so Playwright Inspector opens when the test pauses for a manual CAPTCHA step.

### macOS / Linux

```bash
HEADLESS=0 pytest tests/test_e2e_ebay.py -v
```

Enable Playwright tracing (saved to `artifacts/cart_trace.zip`):

```bash
HEADLESS=0 EBAY_TRACE=1 pytest tests/test_e2e_ebay.py -v
```

Step through the test in the Playwright Inspector:

```bash
HEADLESS=0 PWDEBUG=1 pytest tests/test_e2e_ebay.py -v -k mug_bin_under_25
```

> **`PWDEBUG=1` note**: the Inspector pauses at the very first Playwright call. Click **Resume** (▶) to continue. If you close the Inspector window the browser connection drops and the test fails with `TargetClosedError`. Only use `PWDEBUG=1` when you intend to step through the test manually.

### Windows (PowerShell)

```powershell
$env:HEADLESS = "0"
pytest tests/test_e2e_ebay.py -v
```

> Use eBay only in line with their [User Agreement](https://www.ebay.com/help/policies/member-behaviour-policies/user-agreement?id=4259). This project is for learning purposes.

### Test data

Cases are in `data/ebay/cases.json`. Add or edit cases without touching any Python.

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Test ID shown in pytest output |
| `search_text` | yes | Keyword used for the eBay search |
| `max_price` | yes | Per-item ceiling for search (URL + row filter) and cart assertion: allowed total ≤ `max_price × items_added` |
| `add_limit` | no | How many items to collect from search results (default 5) |
| `min_price` | no | Lower price bound for the search URL |
| `buy_it_now_only` | no | `true` (default) — restricts search to Buy It Now listings |
| `login_as_guest` | no | `false` (default) — full sign-in via `credentials.json`; set `true` to open `base_url` only (guest cart; no credentials file read for that case) |

Search collects listing URLs whose **`.s-item__price` (or row) price** is ≤ `max_price` (rows without a parseable price are skipped). The test requires **`len(urls) >= add_limit`** and that **every collected URL is added** to the cart, so a partial add fails loudly.

```json
{
  "name": "mug_bin_under_25",
  "search_text": "ceramic coffee mug",
  "max_price": 100,
  "add_limit": 1,
  "buy_it_now_only": true
}
```

---

## Architecture

```
tests/
  conftest.py              Browser/context/page fixtures; screenshot on failure
  test_e2e_ebay.py         Parametrized E2E test — thin orchestration only

src/pages/
  base_page.py             BasePage (shared goto, assert_url_contains)
  ebay/
    auth_page.py           EbayAuthPage       — login / guest session
    search_results_page.py EbaySearchResultsPage — filtered search URL, XPath SERP rows, price cell, paging
    item_page.py           EbayItemPage       — variant selection, add-to-cart loop, screenshots
    cart_page.py           EbayCartPage       — subtotal parsing, assertion, cart screenshot/trace
    challenge.py           CAPTCHA detection + page.pause() helpers

src/utils/
  data_loader.py           JSON file loader
  money.py                 parse_money — extracts a USD float from any text string

data/ebay/cases.json       Data-driven inputs
artifacts/                 Runtime output: screenshots, trace zip
docs/
  MATALA_EBAY_E2E.md       Hebrew assignment description
  ReadMeAIBugs.md          Static code-review exercise (bug identification)
```

### Data flow

```
data/ebay/cases.json
        │
        ▼  load_test_data()
test_e2e_ebay.py  (one run per case)
        │
        ├─▶ EbayAuthPage.login()
        │
        ├─▶ EbaySearchResultsPage
        │     search_items_by_name_under_price()  URL params + XPath rows + .s-item__price ≤ max → URLs + Next
        │
        ├─▶ EbayItemPage.add_items_to_cart(urls)
        │     for each URL:
        │       goto(url)
        │       select_variants_if_present()   random dropdown / swatch pick
        │       add_to_cart()
        │       screenshot → artifacts/ + Allure
        │
        └─▶ EbayCartPage.assert_cart_total_not_exceeds(budget_per_item, items_count)
              get_subtotal()             multi-selector + regex fallback
              assert subtotal ≤ budget × count
              cart screenshot → Allure
              tracing.stop() → artifacts/cart_trace.zip
```

---

## Reports

### Allure (recommended)

```bash
HEADLESS=0 pytest tests/test_e2e_ebay.py -v --alluredir=allure-results
allure serve allure-results
```

### HTML

```bash
HEADLESS=0 pytest tests/test_e2e_ebay.py -v --html=report.html --self-contained-html
```

### JUnit XML (CI)

```bash
HEADLESS=0 pytest tests/test_e2e_ebay.py -v --junitxml=junit.xml
```

### All at once

```bash
HEADLESS=0 PWDEBUG=1 pytest tests/test_e2e_ebay.py -v \
  --alluredir=allure-results \
  --html=report.html --self-contained-html \
  --junitxml=junit.xml
```

---

## Implementation summary

All four functions required by the assignment are implemented and wired into a single parametrised pytest test (`test_ebay_search_filter_cart_assert_total`).

| # | Assignment function | Implementation | File |
|---|---------------------|----------------|------|
| 1 | **Authentication** | `EbayAuthPage.login(username, password)` — two-step eBay sign-in with CAPTCHA/2FA `page.pause()` support; `login_as_guest()` for guest sessions; driven by `login_as_guest` flag in `cases.json` | `src/pages/ebay/auth_page.py` |
| 2 | **searchItemsByNameUnderPrice** | `EbaySearchResultsPage.search_items_by_name_under_price(query, max_price, limit=5)` — navigates to eBay with `_udhi`/`_udlo` URL price params, walks `ul.srp-results li.s-item, li.s-card` rows and parses `.s-item__price` via `lowest_price_in_listing_text()`, follows `a.pagination__next` across pages until `limit` qualifying URLs are collected, returns fewer items (even 0) if pagination runs out | `src/pages/ebay/search_results_page.py` |
| 3 | **addItemsToCart** | `EbayItemPage.add_items_to_cart(urls)` — loops through each URL, `select_variants_if_present()` picks random `<select>` options and swatch buttons, clicks "Add to cart" and waits for the confirmation modal, saves a screenshot to `artifacts/` and attaches it to Allure per item | `src/pages/ebay/item_page.py` |
| 4 | **assertCartTotalNotExceeds** | `EbayCartPage.assert_cart_total_not_exceeds(budget_per_item, items_count)` — opens `cart.ebay.com`, parses subtotal via a priority-ranked regex chain (USD, then local currency), asserts `subtotal ≤ budget_per_item × items_count`, saves a full-page cart screenshot and optional Playwright trace | `src/pages/ebay/cart_page.py` |

