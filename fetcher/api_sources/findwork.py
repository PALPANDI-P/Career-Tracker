"""
Career Tracker — Findwork.dev API Source

Fetches developer and tech jobs from Findwork.dev REST API.
"""

from __future__ import annotations

import logging
import os
import requests

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)


class FindworkFetcher:
    """Fetch jobs from Findwork.dev API."""

    name = "findwork"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("FINDWORK_API_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch_jobs(self, location: str = "", keywords: str = "", limit: int = 25) -> list[Job]:
        return fetch_findwork_jobs(api_key=self.api_key, limit=limit)


def fetch_findwork_jobs(
    api_key: str | None = None,
    limit: int = 25,
) -> list[Job]:
    """Fetch developer jobs from Findwork.dev API."""
    key = api_key or os.getenv("FINDWORK_API_KEY")
    if not key:
        logger.debug("Findwork API key not set; skipping Findwork source.")
        return []

    jobs: list[Job] = []
    url = "https://findwork.dev/api/jobs/"
    headers = {"Authorization": f"Token {key}"}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            for item in results:
                title = item.get("role", "").strip()
                company = item.get("company_name", "Tech Company").strip()
                link = item.get("url", "")
                desc = item.get("text", "")
                loc = item.get("location", "Remote / India")

                if not title or not link:
                    continue

                ext_id = f"findwork-{item.get('id', hash(link) & 0xffffff)}"
                job_id = Job.make_id(company, external_id=ext_id)

                job = Job(
                    id=job_id,
                    external_id=ext_id,
                    title=title,
                    company=company,
                    location=loc,
                    url=link,
                    description=desc[:500],
                    source_type=SourceType.API_SOURCE,
                    ats_type=ATSType.CUSTOM,
                    tags=["findwork-api", "tech-jobs"],
                )
                jobs.append(job)
                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.debug("Error fetching Findwork jobs: %s", e)

    logger.info("Findwork API: fetched %d jobs", len(jobs))
    return jobs

