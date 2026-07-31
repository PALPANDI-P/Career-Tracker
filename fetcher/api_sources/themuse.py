"""
Career Tracker — The Muse API Fetcher

Free tier: 500 requests/hour.
Docs: https://www.themuse.com/developers/api/v2
Provides company profiles + jobs.
"""

from __future__ import annotations

import logging

import requests

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)

THEMUSE_URL = "https://www.themuse.com/api/public/jobs"


class TheMuseFetcher:
    """Fetch tech jobs from The Muse API."""

    name = "themuse"

    @property
    def is_configured(self) -> bool:
        return True  # Free public API, no key required for basic access

    def fetch_jobs(
        self,
        location: str = "",
        keywords: str = "Software Engineer",
        page: int = 0,
    ) -> list[Job]:
        """Fetch jobs from The Muse API."""
        params: dict = {
            "category": "Software Engineering",
            "level": "Entry Level",
            "page": page,
        }

        if location:
            params["location"] = location

        try:
            resp = requests.get(THEMUSE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("The Muse API request failed: %s", e)
            return []
        except ValueError:
            logger.error("The Muse API returned invalid JSON")
            return []

        jobs: list[Job] = []
        for item in data.get("results", []):
            try:
                title = item.get("name", "")
                company_data = item.get("company", {})
                company = company_data.get("name", "Unknown")
                if not title:
                    continue

                # Parse locations
                locations = item.get("locations", [])
                loc_names = [loc.get("name", "") for loc in locations if loc.get("name")]
                display_location = ", ".join(loc_names[:2]) or "Not specified"

                # Parse levels
                levels = item.get("levels", [])
                level_names = [lvl.get("name", "") for lvl in levels]

                tags = ["themuse", "api-source"]
                tags.extend(level_names)

                job = Job(
                    id=Job.make_id("themuse", str(item.get("id", ""))),
                    external_id=str(item.get("id", "")),
                    title=title,
                    company=company,
                    location=display_location,
                    url=item.get("refs", {}).get("landing_page", ""),
                    description=item.get("contents", ""),
                    source_type=SourceType.HTML_PARSED,
                    ats_type=ATSType.CUSTOM,
                    tags=tags,
                )
                jobs.append(job)
            except Exception as e:
                logger.warning("Failed to parse The Muse job: %s", e)
                continue

        logger.info("The Muse: fetched %d jobs", len(jobs))
        return jobs


def fetch_themuse_jobs(location: str = "", keywords: str = "software engineer") -> list[Job]:
    """Module-level helper to fetch The Muse jobs."""
    fetcher = TheMuseFetcher()
    return fetcher.fetch_jobs(location=location, keywords=keywords)

