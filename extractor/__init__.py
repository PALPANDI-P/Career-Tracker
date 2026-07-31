"""
Career Tracker — Extraction Dispatcher

Routes extraction through the correct pipeline:
1. Try ATS JSON parser (Greenhouse, Lever, SmartRecruiters)
2. Try HTML CSS selectors (per-company custom rules)
3. Fall back to LLM extraction (Phase 5)

The dispatcher ensures we only call the LLM when deterministic
parsing has failed — keeping costs low and reliability high.
"""

from __future__ import annotations

import logging

from schema.job import CompanyConfig, Job
from fetcher.fetch import FetchResult
from extractor.ats_parsers import get_parser, has_parser
from extractor.llm_fallback import extract_jobs_llm

logger = logging.getLogger(__name__)


def extract_jobs(
    config: CompanyConfig,
    fetch_result: FetchResult,
) -> list[Job]:
    """
    Extract job listings from a fetched page.

    Tries extraction methods in order of reliability:
    1. ATS JSON parser (if the company uses a known ATS)
    2. Custom HTML selectors (if configured for the company)
    3. LLM fallback (if all else fails — Phase 5)

    Args:
        config: Company configuration
        fetch_result: Result from the fetcher

    Returns:
        List of extracted Job objects
    """
    # ── Step 1: Try ATS JSON parser ──────────────────
    if has_parser(config.ats_type):
        parser = get_parser(config.ats_type)
        if parser is not None:
            try:
                jobs = parser(fetch_result.content, config.name)
                if jobs:
                    logger.info(
                        "ATS parser (%s) extracted %d jobs for %s",
                        config.ats_type.value,
                        len(jobs),
                        config.name,
                    )
                    return jobs
                logger.warning(
                    "ATS parser (%s) returned 0 jobs for %s — trying fallbacks",
                    config.ats_type.value,
                    config.name,
                )
            except Exception as e:
                logger.warning(
                    "ATS parser (%s) failed for %s: %s — trying fallbacks",
                    config.ats_type.value,
                    config.name,
                    e,
                )

    # ── Step 2: Try custom HTML selectors ────────────
    if config.custom_selectors:
        try:
            jobs = _extract_with_selectors(config, fetch_result.content)
            if jobs:
                logger.info(
                    "CSS selectors extracted %d jobs for %s",
                    len(jobs),
                    config.name,
                )
                return jobs
        except Exception as e:
            logger.warning(
                "CSS selector extraction failed for %s: %s",
                config.name,
                e,
            )

    # ── Step 3: LLM fallback (Phase 5) ──────────────
    logger.info(
        "No structured parser matched for %s — attempting LLM fallback",
        config.name,
    )
    return extract_jobs_llm(fetch_result.content, config.name)


def _extract_with_selectors(
    config: CompanyConfig,
    html_content: str,
) -> list[Job]:
    """
    Extract jobs using custom CSS selectors defined in company config.

    Placeholder — will be expanded in Phase 5 with per-company selector rules.
    """
    # Phase 5: implement BeautifulSoup-based extraction with config.custom_selectors
    raise NotImplementedError(
        f"CSS selector extraction not yet implemented for '{config.name}'"
    )
