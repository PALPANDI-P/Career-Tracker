"""
Career Tracker — Jooble Job API Source (India & Global Focus)

Queries Jooble REST API for fresher, junior, MCA/BCA, and entry-level IT roles
across India (Chennai, Bangalore, Hyderabad, Coimbatore, Pune, Remote).
"""

from __future__ import annotations

import logging
import os
import requests

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)

JOOBLE_SEARCH_TERMS = [
    "Software Engineer Fresher",
    "Graduate Engineer Trainee",
    "Python Developer Fresher",
    "Associate Software Engineer",
    "MCA Trainee Developer",
]


class JoobleFetcher:
    """Fetch jobs from Jooble API."""

    name = "jooble"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("JOOBLE_API_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch_jobs(
        self,
        location: str = "India",
        keywords: str = "Software Engineer Fresher",
        limit: int = 30,
    ) -> list[Job]:
        return fetch_jooble_jobs(api_key=self.api_key, location=location, limit=limit)


def fetch_jooble_jobs(
    api_key: str | None = None,
    location: str = "India",
    limit: int = 30,
) -> list[Job]:
    """
    Fetch job listings from Jooble API.
    """
    key = api_key or os.getenv("JOOBLE_API_KEY")
    if not key:
        logger.debug("Jooble API key not set; skipping Jooble source.")
        return []

    jobs: list[Job] = []
    url = f"https://jooble.org/api/{key}"
    headers = {"Content-Type": "application/json"}

    for keyword in JOOBLE_SEARCH_TERMS:
        try:
            payload = {
                "keywords": keyword,
                "location": location,
                "page": 1,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code != 200:
                continue

            data = resp.json()
            items = data.get("jobs", [])
            for item in items:
                title = item.get("title", "").strip()
                company = item.get("company", "Tech Company").strip()
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                loc = item.get("location", "India")

                if not title or not link:
                    continue

                ext_id = f"jooble-{hash(link) & 0xffffff}"
                job_id = Job.make_id(company, external_id=ext_id)

                job = Job(
                    id=job_id,
                    external_id=ext_id,
                    title=title,
                    company=company,
                    location=loc,
                    url=link,
                    description=snippet,
                    source_type=SourceType.API_SOURCE,
                    ats_type=ATSType.CUSTOM,
                    tags=["jooble-api", "india-jobs", "fresher-friendly"],
                )
                jobs.append(job)

                if len(jobs) >= limit:
                    break
        except Exception as e:
            logger.debug("Error fetching Jooble jobs for keyword %s: %s", keyword, e)

        if len(jobs) >= limit:
            break

    logger.info("Jooble API: fetched %d jobs", len(jobs))
    return jobs

