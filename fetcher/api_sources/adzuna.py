"""
Career Tracker — Adzuna API Fetcher

Free tier: 100 requests/day.
Docs: https://developer.adzuna.com/
Provides India job listings with salary data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from config.settings import get_settings
from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search"


class AdzunaFetcher:
    """Fetch jobs from Adzuna API (India)."""

    name = "adzuna"

    def __init__(self) -> None:
        settings = get_settings()
        self.app_id = getattr(settings, "adzuna_app_id", None)
        self.api_key = getattr(settings, "adzuna_api_key", None)

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.api_key)

    def fetch_jobs(
        self,
        location: str = "tamil nadu",
        keywords: str = "fresher software engineer",
        page: int = 1,
        results_per_page: int = 50,
        max_days_old: int = 7,
    ) -> list[Job]:
        """Fetch fresher jobs from Adzuna India."""
        if not self.is_configured:
            logger.warning("Adzuna API keys not configured. Skipping.")
            return []

        url = f"{ADZUNA_BASE_URL}/{page}"
        params = {
            "app_id": self.app_id,
            "app_key": self.api_key,
            "what": keywords,
            "where": location,
            "max_days_old": max_days_old,
            "results_per_page": results_per_page,
            "sort_by": "date",
            "content-type": "application/json",
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("Adzuna API request failed: %s", e)
            return []
        except ValueError:
            logger.error("Adzuna API returned invalid JSON")
            return []

        jobs: list[Job] = []
        for result in data.get("results", []):
            try:
                job = Job(
                    id=Job.make_id("adzuna", str(result.get("id", ""))),
                    external_id=str(result.get("id", "")),
                    title=result.get("title", "Untitled"),
                    company=result.get("company", {}).get("display_name", "Unknown"),
                    location=result.get("location", {}).get("display_name", location),
                    url=result.get("redirect_url", ""),
                    description=result.get("description", ""),
                    source_type=SourceType.HTML_PARSED,
                    ats_type=ATSType.CUSTOM,
                    tags=["adzuna", "api-source"],
                )
                jobs.append(job)
            except Exception as e:
                logger.warning("Failed to parse Adzuna job: %s", e)
                continue

        logger.info("Adzuna: fetched %d jobs for '%s' in '%s'", len(jobs), keywords, location)
        return jobs


def fetch_adzuna_jobs(location: str = "India", keywords: str = "fresher software engineer") -> list[Job]:
    """Module-level helper to fetch Adzuna jobs."""
    fetcher = AdzunaFetcher()
    return fetcher.fetch_jobs(location=location, keywords=keywords)

