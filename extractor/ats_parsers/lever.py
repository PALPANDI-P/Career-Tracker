"""
Career Tracker — Lever ATS Parser

Parses job listings from Lever's JSON API.
Lever postings are available at:
  https://api.lever.co/v0/postings/{company}?mode=json

The JSON schema is stable — no LLM needed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)


def parse_lever_jobs(
    raw_json: str,
    company_name: str,
) -> list[Job]:
    """
    Parse Lever API JSON response into Job objects.

    Args:
        raw_json: Raw JSON string from Lever API
        company_name: Company name for the Job.company field

    Returns:
        List of validated Job objects
    """
    data = json.loads(raw_json)

    # Lever returns a flat array of postings (no wrapper key)
    if not isinstance(data, list):
        logger.warning("Unexpected Lever response format for %s: not a list", company_name)
        return []

    if not data:
        logger.warning("No jobs found in Lever response for %s", company_name)
        return []

    jobs: list[Job] = []

    for posting in data:
        try:
            job = _parse_single_posting(posting, company_name)
            jobs.append(job)
        except Exception as e:
            logger.warning(
                "Failed to parse Lever posting for %s: %s (data: %s)",
                company_name,
                e,
                _safe_preview(posting),
            )
            continue

    logger.info("Parsed %d jobs from Lever for %s", len(jobs), company_name)
    return jobs


def _parse_single_posting(posting: dict[str, Any], company_name: str) -> Job:
    """Parse a single Lever posting into a Job object."""
    external_id = posting.get("id", "")
    title = posting.get("text", "").strip()

    # Location: Lever uses "categories.location" or top-level "workplaceType"
    categories = posting.get("categories", {})
    location = categories.get("location", "")

    # URL: hostedUrl is the canonical posting URL
    url = posting.get("hostedUrl", "")
    if not url:
        # Fallback: applyUrl
        url = posting.get("applyUrl", "")

    # Description: Lever provides "descriptionPlain" or structured "lists"
    description = posting.get("descriptionPlain", "")
    if not description:
        # Fallback: concatenate all list items
        description = _build_description_from_lists(posting.get("lists", []))

    # Additional text from the opening description
    additional = posting.get("additionalPlain", "")
    if additional:
        description = f"{description}\n\n{additional}".strip()

    # Department: categories.team or categories.department
    department = categories.get("team") or categories.get("department")

    # Posted date: createdAt is a Unix timestamp in milliseconds
    posted_date = _parse_lever_timestamp(posting.get("createdAt"))

    job_id = Job.make_id(company_name, external_id=external_id)

    return Job(
        id=job_id,
        external_id=external_id,
        title=title,
        company=company_name,
        location=location or None,
        url=url,
        description=description,
        department=department,
        source_type=SourceType.ATS_JSON,
        ats_type=ATSType.LEVER,
        posted_date=posted_date,
    )


def _parse_lever_timestamp(ms_timestamp: int | None) -> datetime | None:
    """Parse Lever Unix timestamp (milliseconds) to datetime."""
    if not ms_timestamp:
        return None
    try:
        return datetime.fromtimestamp(ms_timestamp / 1000, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        logger.debug("Failed to parse Lever timestamp: %s", ms_timestamp)
        return None


def _build_description_from_lists(lists: list[dict[str, Any]]) -> str:
    """
    Build description text from Lever's structured "lists" field.

    Each list has a "text" (heading) and "content" (HTML bullet points).
    """
    parts: list[str] = []
    for section in lists:
        heading = section.get("text", "")
        content = section.get("content", "")
        if heading:
            parts.append(heading)
        if content:
            # Strip HTML from content
            parts.append(_strip_html(content))
    return "\n\n".join(parts)


def _strip_html(html: str) -> str:
    """Strip HTML tags from a string."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        import re

        clean = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", clean).strip()


def _safe_preview(data: Any, max_len: int = 200) -> str:
    """Create a safe preview of data for logging."""
    text = str(data)
    return text[:max_len] + "..." if len(text) > max_len else text
