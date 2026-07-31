"""
Career Tracker — Jobicy Free API Source

Fetches remote software engineering and IT jobs from Jobicy public API (No key required).
"""

from __future__ import annotations

import logging
import requests

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)


class JobicyFetcher:
    """Fetch jobs from Jobicy API."""

    name = "jobicy"

    @property
    def is_configured(self) -> bool:
        return True

    def fetch_jobs(self, location: str = "", keywords: str = "", limit: int = 25) -> list[Job]:
        return fetch_jobicy_jobs(limit=limit)


def fetch_jobicy_jobs(limit: int = 25) -> list[Job]:
    """Fetch remote IT jobs from Jobicy public API."""
    jobs: list[Job] = []
    url = "https://jobicy.com/api/v2/remote-jobs?count=30&geo=india,remote"

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("jobs", [])
            for item in items:
                title = item.get("jobTitle", "").strip()
                company = item.get("companyName", "Tech Company").strip()
                link = item.get("url", "")
                desc = item.get("jobDescription", "")
                loc = item.get("jobGeo", "Remote / India")

                if not title or not link:
                    continue

                ext_id = f"jobicy-{item.get('id', hash(link) & 0xffffff)}"
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
                    tags=["jobicy-api", "remote-tech"],
                )
                jobs.append(job)
                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.debug("Error fetching Jobicy jobs: %s", e)

    logger.info("Jobicy API: fetched %d jobs", len(jobs))
    return jobs

