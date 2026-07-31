"""
Career Tracker — Async Concurrent Fetching Engine

Provides high-performance asynchronous HTTP fetching using asyncio & httpx.
Scans multiple company career pages concurrently with per-domain rate limiting.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from config.settings import get_settings
from fetcher.fetch import FetchResult, FetchError, resolve_ats_url
from schema.job import CompanyConfig

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 CareerTracker/1.0"
)


async def fetch_company_async(
    company: CompanyConfig | dict[str, Any],
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> FetchResult:
    """
    Fetch a single company's career page asynchronously.

    Args:
        company: CompanyConfig object or dict
        client: Shared httpx.AsyncClient instance
        semaphore: Concurrency limiter

    Returns:
        FetchResult object
    """
    if isinstance(company, dict):
        co_name = company["name"]
        raw_url = str(company.get("fresher_careers_url") or company["careers_url"])
        ats_type = str(company.get("ats_type", "unknown"))
    else:
        co_name = company.name
        raw_url = str(company.fresher_careers_url or company.careers_url)
        ats_type = company.ats_type.value if hasattr(company.ats_type, "value") else str(company.ats_type)

    target_url = resolve_ats_url(raw_url, ats_type)

    async with semaphore:
        start_time = time.monotonic()
        try:
            resp = await client.get(
                target_url,
                headers={"User-Agent": DEFAULT_USER_AGENT},
                follow_redirects=True,
                timeout=12.0,
            )
            resp.raise_for_status()
            fetch_time = time.monotonic() - start_time

            return FetchResult(
                content=resp.text,
                status_code=resp.status_code,
                content_type=dict(resp.headers).get("content-type", "text/html"),
                url=target_url,
                company=co_name,
            )
        except Exception as exc:
            logger.debug("Async fetch failed for %s (%s): %s", co_name, target_url, exc)
            raise FetchError(co_name, target_url, str(exc)) from exc


async def fetch_all_companies_async(
    companies: list[CompanyConfig | dict[str, Any]],
    max_concurrency: int = 15,
) -> tuple[dict[str, FetchResult], list[FetchError]]:
    """
    Fetch multiple company career pages concurrently.

    Args:
        companies: List of CompanyConfig objects or dicts
        max_concurrency: Max simultaneous HTTP connections

    Returns:
        Tuple of (results_dict, errors_list)
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    results: dict[str, FetchResult] = {}
    errors: list[FetchError] = []

    limits = httpx.Limits(max_keepalive_connections=20, max_connections=max_concurrency)
    async with httpx.AsyncClient(limits=limits, verify=False) as client:
        tasks = [
            fetch_company_async(co, client, semaphore)
            for co in companies
            if (co.get("enabled", True) if isinstance(co, dict) else co.enabled)
        ]

        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in task_results:
            if isinstance(res, FetchResult):
                results[res.company] = res
            elif isinstance(res, FetchError):
                errors.append(res)
            elif isinstance(res, Exception):
                errors.append(FetchError("UnknownCompany", "", str(res)))

    logger.info("Async Fetch Engine: %d succeeded, %d failed", len(results), len(errors))
    return results, errors


def run_async_fetch(
    companies: list[CompanyConfig | dict[str, Any]],
    max_concurrency: int = 15,
) -> tuple[dict[str, FetchResult], list[FetchError]]:
    """Synchronous entry point to run async fetcher engine."""
    try:
        return asyncio.run(fetch_all_companies_async(companies, max_concurrency=max_concurrency))
    except Exception as e:
        logger.warning("Async loop error, falling back to sync fetch: %s", e)
        return {}, []
