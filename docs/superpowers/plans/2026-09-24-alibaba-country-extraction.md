# Alibaba Buyer Country Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize Alibaba crawler and API client to accurately extract buyer country/region from inquiry lists, IM panels, detail cards/drawers, and propagate it to the CRM synchronization payload.

**Architecture:**
- Refactor DOM evaluation script in `alibaba_bot.py` to extract country without false-matching avatar images, looking for flag icons, flag CSS classes, country text tags, and detail page buyer profiles.
- Maintain an in-memory cache of inquiry-to-country mappings on `AlibabaMessengerBot` and expose `get_last_extracted_country(inquiry_id)` and `get_buyer_profile(inquiry_id, buyer_name)`.
- Update `sync_service.py` to backfill missing conversation country using the extracted/cached country before generating sync payloads.
- Update `server.py` `/api/message/history` and add `/api/buyer/profile` endpoint to surface buyer country.
- Add `extract_order_country` helper in `alibaba_crm_client.py` for OpenAPI order responses.

**Tech Stack:** Python 3.14, Playwright, FastAPI, Pydantic, Pytest

**Spec:** User request: "优化一下alibb的api把国家也爬出来"

## Global Constraints
- Outbound safety: `FUSANHE_OUTBOUND_PAUSED=true` must remain enforced; no real outbound messages.
- Privacy: Do not leak real buyer personal info, auth tokens, or sensitive message content.
- Backward compatibility: All 72 existing tests in `alibaba-client/tests` must pass.
- Architecture: Code changes located in `G:\FSH\CRM\fsh\alibaba-client`.

## Review Focus
1. Avatar image false-positive: `img[alt]` matches `<img alt="">` or `<img alt="avatar">` before flag images. Must explicitly exclude avatar/logo images and only match flag/country classes or valid country code patterns.
2. ISO 2-letter country code vs country full name: Standardize and handle both 2-letter codes (e.g., "US", "DE") and full names (e.g., "United States", "Germany").
3. Multiple page formats: Handle both inquiry list view (`maInquiryList.htm`), detail page (`maDetail.htm`), and IM floating drawer.
4. Fallback when country is missing on list: Detail page extraction must populate the country cache so `sync_service` receives country during history fetch.
5. Missing country in IM fallback: Traditional IM session items must also extract country if present, or gracefully return empty string without failing.

---

### Task 1: DOM Country Extraction Logic in `alibaba_bot.py`

**Files:**
- Modify: `alibaba_messenger/alibaba_bot.py:620-645, 240-275`
- Test: `tests/test_read_messages.py`

**Interfaces:**
- Consumes: Playwright page DOM
- Produces: `country` string in inquiry item dictionary

- [ ] **Step 1: Write the failing test for country extraction in `tests/test_read_messages.py`**

```python
@pytest.mark.asyncio
async def test_bot_extract_country_from_inquiry_item():
    bot_instance = AlibabaMessengerBot()
    # Test that flag image or country tag is extracted and avatar is ignored
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_read_messages.py -k test_bot_extract_country -v`
Expected: FAIL

- [ ] **Step 3: Implement robust country extraction in `alibaba_bot.py`**
- Fix JS evaluation in `get_recent_conversations` (lines 624-635):
  Exclude avatar/product/logo images (`img:not([class*="avatar"]):not([src*="avatar"]):not([class*="logo"])`).
  Match country from `img[src*="flag"], img[src*="country"], img[src*="nation"], [class*="flag"], [class*="country"], [class*="nation"], [data-country]`.
  Support 2-letter code extraction from image filenames `/\/([a-zA-Z]{2})\.(png|jpg|svg|webp)/i` and CSS classes `flag-([a-zA-Z]{2})`.
- Also update `_find_inquiry_row` to extract and return `country`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_read_messages.py -v`
Expected: PASS

---

### Task 2: Country Extraction in Detail Page, IM Fallback, and Bot Cache

**Files:**
- Modify: `alibaba_messenger/alibaba_bot.py:720-745, 1280-1320`
- Test: `tests/test_read_messages.py`

**Interfaces:**
- Consumes: Detail page DOM (`detail_page`) or drawer
- Produces: `self._inquiry_countries`, `bot.get_last_extracted_country(inquiry_id)`, `bot.get_buyer_profile(buyer_name, inquiry_id)`

- [ ] **Step 1: Add failing test for detail page country extraction and `get_buyer_profile`**

```python
@pytest.mark.asyncio
async def test_bot_get_buyer_profile():
    bot_instance = AlibabaMessengerBot()
    bot_instance.is_logged_in = True
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_read_messages.py -k test_bot_get_buyer_profile -v`
Expected: FAIL

- [ ] **Step 3: Implement detail page country extraction & profile method in `alibaba_bot.py`**
- Add `self._inquiry_countries = {}` in `AlibabaMessengerBot.__init__`.
- In `get_chat_history`: extract country from detail page/drawer buyer profile header/sidebar (e.g. `.buyer-profile`, `.customer-info`, or text with "国家/地区").
- Store country in `self._inquiry_countries[inquiry_id]` and return in `res["data"]["country"]`.
- Add `get_last_extracted_country(self, inquiry_id: str) -> str`.
- Add `get_buyer_profile(self, buyer_name=None, inquiry_id=None)` method.
- In IM fallback (lines 720-745), query country elements and include `"country"` in the item dict.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_read_messages.py -v`
Expected: PASS

---

### Task 3: Sync Service & Payload Normalization (`sync_service.py` & `sync_models.py`)

**Files:**
- Modify: `alibaba_messenger/sync_service.py:60-90, 130-160`
- Modify: `alibaba_messenger/sync_models.py:54-67`
- Test: `tests/test_sync_models.py`, `tests/test_sync_service.py`

**Interfaces:**
- Consumes: `conversation` dict, `bot.get_last_extracted_country`
- Produces: Normalized `country` in sync payload sent to CRM

- [ ] **Step 1: Add test for country backfilling and normalization in `tests/test_sync_models.py` and `tests/test_sync_service.py`**

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sync_models.py tests/test_sync_service.py -k country -v`
Expected: FAIL

- [ ] **Step 3: Implement country propagation in `sync_service.py` and `sync_models.py`**
- In `sync_service.py`: when `conversation.get("country")` is empty, check `self.bot.get_last_extracted_country(inquiry_id)`.
- If updated during `get_sync_history`, populate `conversation["country"]` before building payload.
- In `sync_models.py`: clean/strip country string and map common 2-letter ISO codes to canonical names if appropriate, or preserve clean string.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sync_models.py tests/test_sync_service.py -v`
Expected: PASS

---

### Task 4: Server API Endpoints (`server.py`) & CRM Client Helper (`alibaba_crm_client.py`)

**Files:**
- Modify: `alibaba_messenger/server.py`
- Modify: `alibaba_crm_client.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `GET /api/buyer/profile`
- Produces: API response with buyer details and country

- [ ] **Step 1: Add test for `GET /api/buyer/profile` in `tests/test_server.py`**

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server.py -k test_buyer_profile -v`
Expected: FAIL

- [ ] **Step 3: Implement `GET /api/buyer/profile` in `server.py` and helper in `alibaba_crm_client.py`**
- Add endpoint `GET /api/buyer/profile` with `buyer_name` and `inquiry_id` query parameters.
- Add `extract_order_country(order_data: dict) -> str` in `alibaba_crm_client.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_server.py -v`
Expected: PASS

---

### Task 5: End-to-End Verification & Git Synchronization

**Files:**
- Test all tests in `alibaba-client/tests`
- Verify contract with CRM `tests/test_phase1.py` and `tests/test_alibaba_sync_contract.py`
- Commit and push to repository

- [ ] **Step 1: Run full test suite in `alibaba-client`**
Run: `python -m pytest tests`
Expected: 100% PASS

- [ ] **Step 2: Run CRM contract tests in root**
Run: `python -m pytest tests/test_phase1.py tests/test_alibaba_sync_contract.py`
Expected: 100% PASS

- [ ] **Step 3: Commit and push changes**
Commit with descriptive message and push to `origin/main`.
