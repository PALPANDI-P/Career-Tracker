# Career Tracker — Implementation Plan

## Requirements Summary

1. **Audit & fix API source registration** — verify all 13 free job APIs are wired into the scheduled pipeline (currently only ~10 are loaded in `api_pipeline.py::_load_api_sources()`).
2. **Event-driven email alerts** — send email only when genuinely new jobs are discovered in a cycle, not just because the scheduler ticked. Eliminate duplicate sends within the same cycle.
3. **Genuine non-repeated messages** — improve dedup to use `content_hash` (title+company+description+location) instead of only `raw_html_hash`, preventing the same job re-appearing in subsequent emails when its description is empty/null.
4. **Strengthen free API coverage** — improve the Google Jobs fetcher (currently hardcoded 3 sample entries) and ensure Remotive + LinkedIn/Naukri + Google Jobs are loaded in the API pipeline.

---

## Task 1 — Fix `_load_api_sources()` to include all 13 fetchers

**File:** `orchestrator/api_pipeline.py`

The current `_load_api_sources()` is missing 4 fetchers that exist in `fetcher/api_sources/__init__.py`:
- `GoogleJobsFetcher`
- `LinkedInNaukriFetcher`
- `RemotiveFetcher`
- `ArbeitnowFetcher` (already listed in `__init__.py` `fetch_all_api_jobs()` but NOT in `_load_api_sources`)

Add try/except blocks for these 4 sources at the end of `_load_api_sources()`:

```python
try:
    from fetcher.api_sources.remotive import RemotiveFetcher
    sources.append(RemotiveFetcher())
except ImportError:
    logger.debug("Remotive fetcher not available")

try:
    from fetcher.api_sources.google_jobs import GoogleJobsFetcher
    sources.append(GoogleJobsFetcher())
except ImportError:
    logger.debug("Google Jobs fetcher not available")

try:
    from fetcher.api_sources.linkedin_naukri_fetcher import LinkedInNaukriFetcher
    sources.append(LinkedInNaukriFetcher())
except ImportError:
    logger.debug("LinkedIn/Naukri fetcher not available")
```

**Verification:** After change, `_load_api_sources()` should return exactly the same 13 sources that `fetch_all_api_jobs()` iterates.

---

## Task 2 — Fix dedup: use `content_hash` as primary dedup key

**File:** `dedup/store.py`

The `is_new()` and `filter_new()` methods currently use `job.raw_html_hash or job.id` as the lookup key. When `raw_html_hash` is empty (many API sources leave it blank), the system falls back to `job.id`, which is generated from external_id + company — meaning the same job posting can slip through if fetched from a different source or if the ID is regenerated.

The `Job` schema already computes `content_hash` (SHA-256 of normalized title+company+description+location) via the `ensure_hashes` model validator. Use it as the primary dedup key.

**Changes in `dedup/store.py`:**

In `is_new()`:
```python
lookup_key = job.content_hash or job.raw_html_hash or job.id
```

In `mark_seen()`:
```python
lookup_key = job.content_hash or job.raw_html_hash or job.id
```

In `filter_new()` — add a secondary dedup pass using `content_hash` for jobs already in the current batch:
```python
def filter_new(self, jobs: list[Job]) -> list[Job]:
    new_jobs: list[Job] = []
    seen_in_batch: set[str] = set()
    for job in jobs:
        lookup_key = job.content_hash or job.raw_html_hash or job.id
        if lookup_key in seen_in_batch:
            continue
        if self.is_new(job):
            new_jobs.append(job)
            self.mark_seen(job)
            seen_in_batch.add(lookup_key)
    ...
```

---

## Task 3 — Fix email alert: send only when there are genuinely new matched jobs

**Problem today:**
- `orchestrator/run.py::main()` calls `send_email_digest(matched, ...)` unconditionally at the end of every run. If `matched` is empty, `send_email_digest` queries the DB for `is_emailed=0` rows and may send stale jobs from a previous failed cycle.
- `hourly_job_bot.py::execute_hourly_scan()` calls `run_pipeline()` (which already sent or attempted an email), then re-queries the DB and calls `send_email_digest()` again — double-sending.
- There is no guard to prevent sending when no new jobs were found in THIS cycle.

**Fix A — `orchestrator/run.py`:** Only call `send_email_digest()` when `matched` is non-empty.

Replace:
```python
notify_matches(matched)
try:
    from notifier.email_notifier import send_email_digest
    send_email_digest(matched, settings.email_to)
except Exception as e:
    ...
```

With:
```python
notify_matches(matched)
if matched:
    try:
        from notifier.email_notifier import send_email_digest
        send_email_digest(matched, settings.email_to)
    except Exception as e:
        logger.warning("Email notification failed: %s", e)
```

**Fix B — `orchestrator/api_pipeline.py`:** Same guard — only call `send_email_digest` when `matched` is non-empty.

Replace:
```python
from notifier import notify_matches
notify_matches(matched)
from notifier.email_notifier import send_email_digest
send_email_digest(matched, settings.email_to)
```

With:
```python
from notifier import notify_matches
notify_matches(matched)
if matched:
    try:
        from notifier.email_notifier import send_email_digest
        send_email_digest(matched, settings.email_to)
    except Exception as e:
        logger.warning("Email notification failed: %s", e)
```

**Fix C — `hourly_job_bot.py`:** Remove the redundant DB query + second `send_email_digest()` call. The pipeline already handles email. Just report whether the pipeline found new matched jobs.

Replace the entire post-pipeline email block (lines 59–83) with:
```python
# Pipeline handles its own email dispatch internally.
# Log the result of the pipeline run.
logger.info(
    "Pipeline dispatched %d matched jobs this cycle.",
    len(matched_jobs_from_pipeline),
)
```

Where `matched_jobs_from_pipeline` is returned from `run_pipeline()` (need to modify `run.py::main()` to return a summary dict with `matched_count`).

**Fix D — `notifier/email_notifier.py`:** Add a guard at the top of `send_email_digest()` so it never falls back to the DB when called with an empty list AND an explicit flag is not set. This prevents stale DB rows from being re-emailed after a partial failure.

Add a new parameter:
```python
def send_email_digest(
    matched_jobs: list,
    recipient_email: str = "palulaptop@gmail.com",
    allow_db_fallback: bool = False,
) -> bool:
```

Only query the DB for `is_emailed=0` rows when `allow_db_fallback=True`. When `allow_db_fallback=False` (default), if `matched_jobs` is empty, return `True` immediately (skip silently).

---

## Task 4 — Improve Google Jobs Fetcher

**File:** `fetcher/api_sources/google_jobs.py`

Current fetcher returns 3 hardcoded sample entries. Replace with a real Google Custom Search or SerpAPI-style scraping using the `serpapi` or `google-api-python-client` libraries, OR add a proper scraper for `https://www.google.com/search?q=site:careers.+fresher+developer+India`.

**Recommended approach (no new API key required):** Scrape the Google Jobs widget from a targeted search query using Playwright (already in the project's fetcher stack). The `fetcher/fetch.py` module already has Playwright support.

```python
from fetcher.fetch import fetch_page
from config.settings import get_settings

GOOGLE_JOBS_SEARCH_URL = "https://www.google.com/search?q={query}&ibp=jobs"

def fetch_jobs(self, location="India", keywords="fresher software engineer") -> list[Job]:
    settings = get_settings()
    query = f"{keywords} jobs in {location}"
    url = GOOGLE_JOBS_SEARCH_URL.format(query=requests.utils.quote(query))
    # Use the project's existing fetch_page with js strategy
    result = fetch_page(
        CompanyConfig(
            name="google_jobs_scrape",
            careers_url=url,
            fetch_strategy="js",
            rate_limit_seconds=1.0,
        )
    )
    # Parse result.html for Google Jobs structured data
    ...
```

If Playwright is too heavy for the API pipeline (it's a separate async path), fallback to a lightweight `requests` + `beautifulsoup4` scrape of a curated list of Google-indexed career pages for specific target companies.

**Minimum viable improvement:** Expand the hardcoded feed from 3 entries to 20–30 verified Google-indexed career pages for companies in the YAML registry that have ATS career pages (Greenhouse, Lever, etc.), pulling their public job listing URLs.

---

## Task 5 — Add notification dedup in email body

**File:** `notifier/email_notifier.py`

In `_build_html_digest()`, deduplicate `matched_jobs` by `(company, title)` before rendering cards, so even if the DB returned duplicates, the email body is clean:

```python
def _dedupe_jobs(items: list) -> list:
    seen: set[tuple[str, str]] = set()
    unique = []
    for item in items:
        title = _extract_field(item, "title") or ""
        company = _extract_field(item, "company") or ""
        key = (company.lower().strip(), title.lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
```

Call `_dedupe_jobs(matched_jobs)` before the card-building loop.

---

## Task 6 — Return run summary from pipeline for bot telemetry

**File:** `orchestrator/run.py`

Modify `main()` to return a summary dict:
```python
return {
    "companies_processed": len(companies),
    "jobs_found": total_jobs,
    "jobs_new": new_jobs,
    "matched_count": len(matched),
    "errors": errors,
}
```

Update `hourly_job_bot.py` to use this return value for logging instead of re-querying the DB.

---

## Validation Steps

1. **API source audit:** Run `python -c "from orchestrator.api_pipeline import _load_api_sources; print([s.name for s in _load_api_sources()])"` — should print 13 source names matching `fetch_all_api_jobs()`.
2. **Dedup test:** Insert two Job objects with same title/company but different `raw_html_hash` (one with empty description). Confirm `store.filter_new()` returns only 1.
3. **Email skip test:** Run `hourly_job_bot.py` with no new jobs in DB. Confirm no SMTP connection is attempted and log shows "Skipping".
4. **Email send test:** Insert 1 new matched job, run pipeline, confirm exactly 1 email sent with that job.
5. **No-duplicate-in-email test:** Insert 2 jobs with same title+company but different IDs. Confirm email contains only 1 card for that job.

---

## Rollout Order

| Step | File(s) | Risk |
|------|---------|------|
| 1. Fix `_load_api_sources()` | `orchestrator/api_pipeline.py` | Low — additive |
| 2. Fix dedup key | `dedup/store.py` | Low — backward compatible (content_hash already computed) |
| 3. Guard email sends | `orchestrator/run.py`, `orchestrator/api_pipeline.py` | Medium — changes notification behavior |
| 4. Remove double-send from bot | `hourly_job_bot.py`, `orchestrator/run.py` | Medium — depends on Step 3 |
| 5. Dedup in email body | `notifier/email_notifier.py` | Low — additive |
| 6. Improve Google Jobs | `fetcher/api_sources/google_jobs.py` | Medium — new scraping logic |

Do Steps 1–2 first (independent, low-risk). Then 3–4 together (they interact). Then 5. Then 6.
