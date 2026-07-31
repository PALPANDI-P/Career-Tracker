"""
Career Tracker — JSearch (RapidAPI) Fetcher

Free tier: 100 requests/month via RapidAPI.
Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
Aggregates Google Jobs data for broad coverage.
"""

from __future__ import annotations

import logging

import requests

from config.settings import get_settings
from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"


class JSearchFetcher:
    """Fetch jobs from JSearch (Google Jobs aggregator) via RapidAPI."""

    name = "jsearch"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = getattr(settings, "jsearch_api_key", None)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch_jobs(
        self,
        location: str = "Chennai, India",
        keywords: str = "fresher software engineer",
        num_pages: int = 1,
    ) -> list[Job]:
        """Fetch jobs from JSearch API."""
        if not self.is_configured:
            logger.warning("JSearch API key not configured. Skipping.")
            return []

        query = f"{keywords} in {location}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }
        params = {
            "query": query,
            "page": "1",
            "num_pages": str(num_pages),
            "date_posted": "week",
        }

        try:
            resp = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("JSearch API request failed: %s", e)
            return []
        except ValueError:
            logger.error("JSearch API returned invalid JSON")
            return []

        jobs: list[Job] = []
        for item in data.get("data", []):
            try:
                title = item.get("job_title", "")
                company = item.get("employer_name", "")
                if not title or not company:
                    continue

                city = item.get("job_city", "")
                state = item.get("job_state", "")
                display_location = ", ".join(filter(None, [city, state])) or location

                job = Job(
                    id=Job.make_id("jsearch", item.get("job_id", "")),
                    external_id=item.get("job_id", ""),
                    title=title,
                    company=company,
                    location=display_location,
                    url=item.get("job_apply_link", "") or item.get("job_google_link", ""),
                    description=item.get("job_description", ""),
                    source_type=SourceType.HTML_PARSED,
                    ats_type=ATSType.CUSTOM,
                    tags=["jsearch", "api-source", "google-jobs"],
                )
                jobs.append(job)
            except Exception as e:
                logger.warning("Failed to parse JSearch job: %s", e)
                continue

        logger.info("JSearch: fetched %d jobs for '%s'", len(jobs), query)
        return jobs


def fetch_jsearch_jobs(location: str = "India", keywords: str = "fresher developer") -> list[Job]:
    """Module-level helper to fetch JSearch jobs."""
    fetcher = JSearchFetcher()
    return fetcher.fetch_jobs(location=location, keywords=keywords)

