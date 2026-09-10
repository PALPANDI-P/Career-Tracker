"""
Career Tracker — Page Fetcher

Fetches career pages using the strategy defined in each company's config:
- 'static': Plain HTTP requests with retries (fast, no browser overhead)
- 'js': Playwright headless browser (Phase 5 — not yet implemented)

This module is entirely deterministic — no LLM calls.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from schema.job import CompanyConfig

logger = logging.getLogger(__name__)

# Rotate through a small pool of User-Agent strings to avoid
# trivial bot detection. These are real browser UAs.
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.5 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
]


class FetchError(Exception):
    """Raised when a page fetch fails after retries."""

    def __init__(self, company: str, url: str, reason: str) -> None:
        self.company = company
        self.url = url
        self.reason = reason
        super().__init__(f"Failed to fetch {company} ({url}): {reason}")


class FetchResult:
    """Result of a page fetch operation."""

    def __init__(
        self,
        content: str,
        status_code: int,
        content_type: str,
        url: str,
        company: str,
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.content_type = content_type
        self.url = url
        self.company = company

    @property
    def is_json(self) -> bool:
        """Check if the response is JSON based on content-type."""
        return "application/json" in self.content_type.lower()

    def __repr__(self) -> str:
        return (
            f"FetchResult(company={self.company!r}, status={self.status_code}, "
            f"content_type={self.content_type!r}, length={len(self.content)})"
        )


def _build_session(
    max_retries: int = 3,
    timeout: int = 30,
) -> requests.Session:
    """
    Build an HTTP session with automatic retries and backoff.

    Uses urllib3's Retry to handle transient failures (429, 500, 502, 503, 504)
    with exponential backoff.
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,  # 1s, 2s, 4s between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    return session


def resolve_ats_url(raw_url: str, ats_type: str = "custom") -> str:
    """Convert raw career page URL to public ATS API URL if applicable."""
    url = raw_url.rstrip("/")
    if ats_type == "greenhouse":
        if "boards.greenhouse.io" in url:
            slug = url.split("boards.greenhouse.io/")[-1].split("/")[0]
            return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        return f"{url}/jobs.json"
    elif ats_type == "lever":
        if "jobs.lever.co" in url:
            slug = url.split("jobs.lever.co/")[-1].split("/")[0]
            return f"https://api.lever.co/v0/postings/{slug}"
        return f"{url}/postings"
    elif ats_type == "smartrecruiters":
        if "jobs.smartrecruiters.com" in url:
            slug = url.split("jobs.smartrecruiters.com/")[-1].split("/")[0]
            return f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
        return f"{url}/postings"
    return raw_url


def _get_ats_api_url(config: CompanyConfig) -> str:
    """
    Convert a careers page URL to the corresponding ATS API endpoint.

    Each ATS platform has a well-known JSON API URL pattern:
    - Greenhouse: boards-api.greenhouse.io/v1/boards/{company}/jobs
    - Lever: api.lever.co/v0/postings/{company}
    - SmartRecruiters: api.smartrecruiters.com/v1/companies/{company}/postings
    """
    url = str(config.careers_url).rstrip("/")
    ats = config.ats_type.value

    if ats == "greenhouse":
        if "boards.greenhouse.io" in url:
            slug = url.split("boards.greenhouse.io/")[-1].split("/")[0]
            return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        return f"{url}/jobs.json"

    elif ats == "lever":
        if "jobs.lever.co" in url:
            slug = url.split("jobs.lever.co/")[-1].split("/")[0]
            return f"https://api.lever.co/v0/postings/{slug}?mode=json"
        return f"{url}?mode=json"

    elif ats == "smartrecruiters":
        if "jobs.smartrecruiters.com" in url:
            slug = url.split("jobs.smartrecruiters.com/")[-1].split("/")[0]
            return f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
        return url

    return url


def fetch_static(
    config: CompanyConfig,
    timeout: int = 30,
    max_retries: int = 3,
    session: Optional[requests.Session] = None,
) -> FetchResult:
    """
    Fetch a career page using plain HTTP requests.

    For known ATS types, automatically resolves to the JSON API endpoint.
    """
    api_url = _get_ats_api_url(config)
    _session = session or _build_session(max_retries=max_retries, timeout=timeout)

    logger.info("Fetching %s: %s", config.name, api_url)

    try:
        response = _session.get(api_url, timeout=timeout)

        if response.status_code >= 400:
            raise FetchError(
                company=config.name,
                url=api_url,
                reason=f"HTTP {response.status_code}: {response.reason}",
            )

        content_type = response.headers.get("Content-Type", "text/html")

        return FetchResult(
            content=response.text,
            status_code=response.status_code,
            content_type=content_type,
            url=api_url,
            company=config.name,
        )

    except requests.exceptions.ConnectionError as e:
        raise FetchError(config.name, api_url, f"Connection error: {e}") from e
    except requests.exceptions.Timeout as e:
        raise FetchError(config.name, api_url, f"Timeout after {timeout}s") from e
    except requests.exceptions.RequestException as e:
        raise FetchError(config.name, api_url, f"Request failed: {e}") from e


def fetch_js(
    config: CompanyConfig,
    timeout: int = 30,
    max_retries: int = 3,
    session: Optional[requests.Session] = None,
    **kwargs: Any,
) -> FetchResult:
    """
    Fetch a page using Playwright headless browser.

    If Playwright is installed, uses Playwright.
    Otherwise, gracefully falls back to enhanced static HTTP fetching.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        logger.info("Fetching %s via Playwright headless browser", config.name)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(str(config.careers_url), timeout=timeout * 1000)
            content = page.content()
            browser.close()
            return FetchResult(
                content=content,
                status_code=200,
                content_type="text/html",
                url=str(config.careers_url),
                company=config.name,
            )
    except Exception as e:
        logger.warning(
            "Playwright unavailable or failed for %s (%s). Falling back to HTTP fetch.",
            config.name, e,
        )
        return fetch_static(config, timeout=timeout, max_retries=max_retries, session=session)



def fetch_page(
    config: CompanyConfig,
    timeout: int = 30,
    max_retries: int = 3,
    session: Optional[requests.Session] = None,
) -> FetchResult:
    """
    Main entry point: fetch a career page using the configured strategy.
    Dispatches to fetch_static or fetch_js based on company config.
    """
    if not config.enabled:
        raise FetchError(config.name, str(config.careers_url), "Company is disabled")

    strategy = config.fetch_strategy

    if strategy == "static":
        return fetch_static(config, timeout=timeout, max_retries=max_retries, session=session)
    elif strategy == "js":
        return fetch_js(config)
    else:
        raise FetchError(
            config.name, str(config.careers_url), f"Unknown fetch strategy: {strategy!r}"
        )


def rate_limit_delay(seconds: float) -> None:
    """Sleep for rate limiting between requests."""
    if seconds > 0:
        time.sleep(seconds)
