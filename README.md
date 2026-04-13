# eBay E2E — Playwright / Python

End-to-end automation for an e-commerce flow on **[eBay.com](https://www.ebay.com/)** using **Playwright**, **pytest**, **Page Object Model**, and **data-driven** test cases from JSON.

---

## What this project does

The test covers four core functions that mirror the assignment spec:

| # | Function | Implementation |
|---|----------|----------------|
| 1 | **Authentication** | `EbayAuthPage.login(user, password, home_url=…)` — real sign-in; pauses on CAPTCHA / interstitial |
| 2 | **searchItemsByNameUnderPrice** | `EbaySearchResultsPage.search_items_by_name_under_price(query, max_price, limit)` — URL `_udhi` / `_udlo`, XPath `li[contains(@class,'s-item')]`, `.s-item__price` ≤ `max_price`, `a.pagination__next` paging |
| 3 | **addItemsToCart** | `EbayItemPage.add_items_to_cart(urls)` — loops URLs, picks random variants, saves screenshot per item |
| 4 | **assertCartTotalNotExceeds** | `EbayCartPage.assert_cart_total_not_exceeds(budget_per_item, items_count)` — asserts subtotal ≤ budget × count, saves cart screenshot + trace |

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

If the file is missing or either field is empty, the test fails immediately with a clear error message before opening the browser.

---

## How to run

The browser is **headless by default**. eBay aggressively blocks headless browsers — run headed and use `PWDEBUG=1` so Playwright Inspector opens when the test pauses for a manual CAPTCHA step.

The test is **skipped by default** unless `EBAY_MANUAL=1` is set.

### macOS / Linux

```bash
HEADLESS=0 EBAY_MANUAL=1 pytest tests/test_e2e_ebay.py -v
```

Pause once after the homepage loads (useful for accepting cookie banners or handling a late challenge):

```bash
HEADLESS=0 EBAY_MANUAL=1 EBAY_ALWAYS_PAUSE=1 pytest tests/test_e2e_ebay.py -v
```

Enable Playwright tracing (saved to `artifacts/cart_trace.zip`):

```bash
HEADLESS=0 EBAY_MANUAL=1 EBAY_TRACE=1 pytest tests/test_e2e_ebay.py -v
```

Step through the test in the Playwright Inspector:

```bash
HEADLESS=0 PWDEBUG=1 EBAY_MANUAL=1 pytest tests/test_e2e_ebay.py -v -k mug_bin_under_25
```

> **`PWDEBUG=1` note**: the Inspector pauses at the very first Playwright call. Click **Resume** (▶) to continue. If you close the Inspector window the browser connection drops and the test fails with `TargetClosedError`. Only use `PWDEBUG=1` when you intend to step through the test manually.

### Windows (PowerShell)

```powershell
$env:HEADLESS = "0"
$env:EBAY_MANUAL = "1"
pytest tests/test_e2e_ebay.py -v
```

> Use eBay only in line with their [User Agreement](https://www.ebay.com/help/policies/member-behaviour-policies/user-agreement?id=4259). This project is for learning purposes.

### Environment variables

| Variable | Default | Effect |
|----------|---------|--------|
| `EBAY_MANUAL` | unset | Must be `1` to run the test (safety gate) |
| `HEADLESS` | `1` | Set to `0` to show the browser window |
| `SLOWMO_MS` | `0` | Milliseconds between actions — useful for visual debugging |
| `BROWSER` | `chromium` | Also accepts `firefox` or `webkit` |
| `LOCALE` | `en-US` | Browser locale |
| `USER_AGENT` | Chrome/124 | Custom user-agent string |
| `EBAY_ALWAYS_PAUSE` | unset | Set to `1` to pause once after the first page load |
| `EBAY_TRACE` | unset | Set to `1` to save a Playwright trace to `artifacts/cart_trace.zip` |
| `NAVIGATION_TIMEOUT_MS` | `90000` | Default timeout for `page.goto` (eBay can be slow) |
| `PLAYWRIGHT_CHANNEL` | unset | Set to `chrome` to use installed Google Chrome instead of bundled Chromium |

If the headed window stays **blank or white**: try `PLAYWRIGHT_CHANNEL=chrome` or `BROWSER=firefox`; check network/VPN/ad-blockers for `ebay.com`.

### Test data

Cases are in `data/ebay/cases.json`. Add or edit cases without touching any Python.

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Test ID shown in pytest output |
| `search_text` | yes | Keyword used for the eBay search |
| `max_price` | yes | Per-item ceiling for search (URL + row filter) and base for cart: allowed total ≤ `max_price × items_added` |
| `cart_total_max` | no | When set, cart subtotal must also be ≤ this number; effective cap is `min(max_price × items_added, cart_total_max)` |
| `add_limit` | no | How many items to collect from search results (default 5) |
| `min_price` | no | Lower price bound for the search URL |
| `buy_it_now_only` | no | `true` (default) — restricts search to Buy It Now listings |

Search collects listing URLs whose **`.s-item__price` (or row) price** is ≤ `max_price` (rows without a parseable price are skipped). The test requires **`len(urls) >= add_limit`** and that **every collected URL is added** to the cart, so a partial add fails loudly.

```json
{
  "name": "mug_bin_under_25",
  "search_text": "ceramic coffee mug",
  "max_price": 100,
  "cart_total_max": 100,
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
HEADLESS=0 EBAY_MANUAL=1 pytest tests/test_e2e_ebay.py -v --alluredir=allure-results
allure serve allure-results
```

### HTML

```bash
HEADLESS=0 EBAY_MANUAL=1 pytest tests/test_e2e_ebay.py -v --html=report.html --self-contained-html
```

### JUnit XML (CI)

```bash
HEADLESS=0 EBAY_MANUAL=1 pytest tests/test_e2e_ebay.py -v --junitxml=junit.xml
```

### All at once

```bash
HEADLESS=0 PWDEBUG=1 EBAY_MANUAL=1 pytest tests/test_e2e_ebay.py -v \
  --alluredir=allure-results \
  --html=report.html --self-contained-html \
  --junitxml=junit.xml
```

---

## Limitations and assumptions

**Authentication** — The test performs a real eBay sign-in (`EbayAuthPage.login()`). eBay's sign-in is a two-step form (username → Continue → password → Sign in). If a CAPTCHA, SMS code, or 2FA screen appears at any point, execution pauses via `page.pause()` — solve it manually in the headed browser, then click **Resume** in the Playwright Inspector. `login_as_guest()` is kept as a fallback if sign-in is not needed.

**Price filtering** — URL parameters (`_udhi` / `_udlo`) match eBay’s facet (e.g. “Under ILS 10.00” when `max_price` is 10). Each result row’s **`.s-item__price`** text is parsed (`$`, `US $`, `ILS`, `GBP`, …); the lowest amount in that cell must be ≤ `max_price`.

**Paging** — `a.pagination__next` until `limit` URLs or no further page.

**Variant selection** — `select_variants_if_present` tries `<select>` dropdowns and swatch button groups, choosing at random. Not all listings expose selectable variants, which is fine — the function is a no-op when nothing is found.

**Currency** — Search row parsing and cart subtotal logic accept multiple currency prefixes; `max_price` in `cases.json` should match the currency eBay applies to the price facet for your account (often local currency on ebay.com).

**Cart subtotal** — `assert_cart_total_not_exceeds` checks the merchandise subtotal, not the final order total. Tax, shipping, and fees are not included.

**CAPTCHA / bot checks** — Headless runs frequently hit "Please verify yourself". Always run with `HEADLESS=0 PWDEBUG=1`. When the test pauses at `page.pause()`, solve the challenge manually in the browser, then click **Resume** in the Playwright Inspector. Never automate CAPTCHA solving.

**Artifacts directory** — Screenshots and the trace zip land in `artifacts/`. Create it before the first run: `mkdir -p artifacts`.
