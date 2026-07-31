"""
Career Tracker — Greenhouse ATS Parser

Parses job listings from Greenhouse's well-documented JSON API.
Greenhouse boards expose jobs at:
  https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true

The JSON schema is stable and well-structured — no LLM needed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)


def parse_greenhouse_jobs(
    raw_json: str,
    company_name: str,
) -> list[Job]:
    """
    Parse Greenhouse API JSON response into Job objects.

    Args:
        raw_json: Raw JSON string from Greenhouse API
        company_name: Company name for the Job.company field

    Returns:
        List of validated Job objects

    Raises:
        json.JSONDecodeError: If the response isn't valid JSON
        KeyError: If the JSON structure doesn't match expected Greenhouse schema
    """
    data = json.loads(raw_json)

    # Greenhouse API wraps jobs in a "jobs" key
    jobs_data = data.get("jobs", [])

    if not jobs_data:
        logger.warning("No jobs found in Greenhouse response for %s", company_name)
        return []

    jobs: list[Job] = []

    for job_data in jobs_data:
        try:
            job = _parse_single_job(job_data, company_name)
            jobs.append(job)
        except Exception as e:
            logger.warning(
                "Failed to parse Greenhouse job for %s: %s (data: %s)",
                company_name,
                e,
                _safe_preview(job_data),
            )
            continue

    logger.info("Parsed %d jobs from Greenhouse for %s", len(jobs), company_name)
    return jobs


def _parse_single_job(job_data: dict[str, Any], company_name: str) -> Job:
    """Parse a single Greenhouse job entry into a Job object."""
    external_id = str(job_data["id"])
    title = job_data.get("title", "").strip()

    # Location: Greenhouse uses a "location" object with "name" field
    location_data = job_data.get("location", {})
    location = location_data.get("name", "") if isinstance(location_data, dict) else ""

    # URL: absolute_url is the canonical job posting URL
    url = job_data.get("absolute_url", "")

    # Description: content field contains HTML description (when ?content=true)
    description = job_data.get("content", "")
    # Strip HTML tags for a cleaner text representation
    if description:
        description = _strip_html(description)

    # Department: nested under departments[0].name
    departments = job_data.get("departments", [])
    department = departments[0].get("name", "") if departments else None

    # Posted date: updated_at or first_published_at
    posted_date = _parse_greenhouse_date(
        job_data.get("updated_at") or job_data.get("first_published_at")
    )

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
        ats_type=ATSType.GREENHOUSE,
        posted_date=posted_date,
    )


def _parse_greenhouse_date(date_str: str | None) -> datetime | None:
    """Parse Greenhouse ISO datetime string."""
    if not date_str:
        return None
    try:
        # Greenhouse uses ISO 8601 format: "2025-07-15T10:30:00-04:00"
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        logger.debug("Failed to parse Greenhouse date: %s", date_str)
        return None


def _strip_html(html: str) -> str:
    """
    Strip HTML tags from a string, producing plain text.

    Uses BeautifulSoup if available, falls back to a simple regex approach.
    """
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
