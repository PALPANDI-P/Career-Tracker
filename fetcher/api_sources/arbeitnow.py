"""
Career Tracker — Arbeitnow API Fetcher

Free, no API key needed.
Docs: https://www.arbeitnow.com/api
Provides remote/hybrid tech jobs.
"""

from __future__ import annotations

import logging

import requests

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowFetcher:
    """Fetch remote/hybrid tech jobs from Arbeitnow."""

    name = "arbeitnow"

    @property
    def is_configured(self) -> bool:
        return True  # No API key needed

    def fetch_jobs(
        self,
        location: str = "",
        keywords: str = "software engineer",
    ) -> list[Job]:
        """Fetch jobs from Arbeitnow API."""
        try:
            resp = requests.get(ARBEITNOW_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("Arbeitnow API request failed: %s", e)
            return []
        except ValueError:
            logger.error("Arbeitnow API returned invalid JSON")
            return []

        jobs: list[Job] = []
        for item in data.get("data", []):
            try:
                title = item.get("title", "")
                company = item.get("company_name", "")
                if not title or not company:
                    continue

                # Filter by keywords
                if keywords:
                    search_text = f"{title} {company} {item.get('description', '')}".lower()
                    if not any(kw.lower() in search_text for kw in keywords.split()):
                        continue

                item_location = item.get("location", "")
                is_remote = item.get("remote", False)
                display_location = "Remote" if is_remote else (item_location or "Not specified")

                tags = ["arbeitnow", "api-source"]
                if is_remote:
                    tags.append("remote")

                job = Job(
                    id=Job.make_id("arbeitnow", item.get("slug", "")),
                    external_id=item.get("slug", ""),
                    title=title,
                    company=company,
                    location=display_location,
                    url=item.get("url", ""),
                    description=item.get("description", ""),
                    source_type=SourceType.HTML_PARSED,
                    ats_type=ATSType.CUSTOM,
                    tags=tags,
                )
                jobs.append(job)
            except Exception as e:
                logger.warning("Failed to parse Arbeitnow job: %s", e)
                continue

        logger.info("Arbeitnow: fetched %d jobs", len(jobs))
        return jobs


def fetch_arbeitnow_jobs(location: str = "", keywords: str = "software engineer") -> list[Job]:
    """Module-level helper to fetch Arbeitnow jobs."""
    fetcher = ArbeitnowFetcher()
    return fetcher.fetch_jobs(location=location, keywords=keywords)

