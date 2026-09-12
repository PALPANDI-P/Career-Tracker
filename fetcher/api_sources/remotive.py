"""
Career Tracker — Remotive Open API Fetcher

Free public API (no API key needed).
Docs: https://remotive.com/api/remote-jobs
Provides developer & software engineering postings.
"""

from __future__ import annotations

import logging
import requests

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)

REMOTIVE_URL = "https://remotive.com/api/remote-jobs?category=software-dev&limit=25"


class RemotiveFetcher:
    """Fetch developer jobs from Remotive API."""

    name = "remotive"

    @property
    def is_configured(self) -> bool:
        return True  # Public free API

    def fetch_jobs(self, location: str = "", keywords: str = "") -> list[Job]:
        """Fetch jobs from Remotive API."""
        try:
            resp = requests.get(REMOTIVE_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.debug("Remotive API request failed: %s", e)
            return []

        jobs: list[Job] = []
        for item in data.get("jobs", [])[:25]:
            try:
                title = item.get("title", "")
                company = item.get("company_name", "")
                if not title or not company:
                    continue

                location_candidate = item.get("candidate_required_location", "") or "Remote / Global"

                job = Job(
                    id=Job.make_id("remotive", str(item.get("id", ""))),
                    external_id=str(item.get("id", "")),
                    title=title,
                    company=company,
                    location=location_candidate,
                    url=item.get("url", "#"),
                    description=item.get("description", ""),
                    source_type=SourceType.HTML_PARSED,
                    ats_type=ATSType.CUSTOM,
                    tags=["remotive", "api-source", "developer-jobs"],
                )
                jobs.append(job)
            except Exception as e:
                logger.debug("Failed to parse Remotive job: %s", e)
                continue

        logger.info("Remotive API: fetched %d developer jobs", len(jobs))
        return jobs


def fetch_remotive_jobs() -> list[Job]:
    """Module-level helper function to fetch Remotive jobs."""
    fetcher = RemotiveFetcher()
    return fetcher.fetch_jobs()
