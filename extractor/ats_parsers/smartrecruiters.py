"""
Career Tracker — SmartRecruiters ATS Parser

Parses job listings from SmartRecruiters' public API.
SmartRecruiters postings are available at:
  https://api.smartrecruiters.com/v1/companies/{company}/postings

The JSON schema is stable — no LLM needed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)


def parse_smartrecruiters_jobs(
    raw_json: str,
    company_name: str,
) -> list[Job]:
    """
    Parse SmartRecruiters API JSON response into Job objects.

    Args:
        raw_json: Raw JSON string from SmartRecruiters API
        company_name: Company name for the Job.company field

    Returns:
        List of validated Job objects
    """
    data = json.loads(raw_json)

    # SmartRecruiters wraps postings in a "content" key
    postings = data.get("content", [])

    if not postings:
        logger.warning("No jobs found in SmartRecruiters response for %s", company_name)
        return []

    jobs: list[Job] = []

    for posting in postings:
        try:
            job = _parse_single_posting(posting, company_name)
            jobs.append(job)
        except Exception as e:
            logger.warning(
                "Failed to parse SmartRecruiters posting for %s: %s (data: %s)",
                company_name,
                e,
                _safe_preview(posting),
            )
            continue

    logger.info("Parsed %d jobs from SmartRecruiters for %s", len(jobs), company_name)
    return jobs


def _parse_single_posting(posting: dict[str, Any], company_name: str) -> Job:
    """Parse a single SmartRecruiters posting into a Job object."""
    external_id = posting.get("id", "") or posting.get("uuid", "")
    # Use ref if id is missing
    if not external_id:
        external_id = posting.get("ref", "")

    title = posting.get("name", "").strip()

    # Location: SmartRecruiters uses a "location" object
    location_data = posting.get("location", {})
    location_parts: list[str] = []
    if location_data.get("city"):
        location_parts.append(location_data["city"])
    if location_data.get("region"):
        location_parts.append(location_data["region"])
    if location_data.get("country"):
        location_parts.append(location_data["country"])
    location = ", ".join(location_parts) if location_parts else None

    # Remote status
    remote_status = location_data.get("remote", False)
    if remote_status and not location:
        location = "Remote"

    # URL: construct from company and posting ref/id
    ref = posting.get("ref", external_id)
    company_data = posting.get("company", {})
    company_identifier = company_data.get("identifier", company_name)
    url = (
        posting.get("applyUrl")
        or f"https://jobs.smartrecruiters.com/{company_identifier}/{ref}"
    )

    # Department
    department_data = posting.get("department", {})
    department = department_data.get("label") if isinstance(department_data, dict) else None

    # Description: releasedDate
    posted_date = _parse_sr_date(posting.get("releasedDate"))

    job_id = Job.make_id(company_name, external_id=str(external_id))

    return Job(
        id=job_id,
        external_id=str(external_id),
        title=title,
        company=company_name,
        location=location,
        url=url,
        description="",  # SmartRecruiters listing API doesn't include full description
        department=department,
        source_type=SourceType.ATS_JSON,
        ats_type=ATSType.SMARTRECRUITERS,
        posted_date=posted_date,
    )


def _parse_sr_date(date_str: str | None) -> datetime | None:
    """Parse SmartRecruiters ISO date string."""
    if not date_str:
        return None
    try:
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        logger.debug("Failed to parse SmartRecruiters date: %s", date_str)
        return None


def _safe_preview(data: Any, max_len: int = 200) -> str:
    """Create a safe preview of data for logging."""
    text = str(data)
    return text[:max_len] + "..." if len(text) > max_len else text
