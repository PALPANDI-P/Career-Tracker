"""
Career Tracker — RemoteOK API Fetcher

Free, no API key needed.
Docs: https://remoteok.com/api
Provides remote tech jobs (globally relevant).
"""

from __future__ import annotations

import logging

import requests

from schema.job import ATSType, Job, SourceType

logger = logging.getLogger(__name__)

REMOTEOK_URL = "https://remoteok.com/api"


class RemoteOKFetcher:
    """Fetch remote tech jobs from RemoteOK."""

    name = "remoteok"

    @property
    def is_configured(self) -> bool:
        return True  # No API key needed

    def fetch_jobs(
        self,
        location: str = "remote",
        keywords: str = "",
    ) -> list[Job]:
        """Fetch jobs from RemoteOK API."""
        headers = {
            "User-Agent": "CareerTracker/1.0 (job aggregation for personal use)"
        }

        try:
            resp = requests.get(REMOTEOK_URL, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("RemoteOK API request failed: %s", e)
            return []
        except ValueError:
            logger.error("RemoteOK API returned invalid JSON")
            return []

        jobs: list[Job] = []
        # RemoteOK returns a list where first item is metadata
        listings = data[1:] if len(data) > 1 else []

        for item in listings:
            try:
                title = item.get("position", "")
                company = item.get("company", "")
                if not title or not company:
                    continue

                # Filter by keywords if provided
                if keywords:
                    search_text = f"{title} {company} {item.get('description', '')}".lower()
                    if not any(kw.lower() in search_text for kw in keywords.split()):
                        continue

                tags_list = item.get("tags", [])
                if isinstance(tags_list, list):
                    tags_list = [str(t) for t in tags_list]
                else:
                    tags_list = []

                job = Job(
                    id=Job.make_id("remoteok", str(item.get("id", ""))),
                    external_id=str(item.get("id", "")),
                    title=title,
                    company=company,
                    location="Remote",
                    url=item.get("url", f"https://remoteok.com/l/{item.get('id', '')}"),
                    description=item.get("description", ""),
                    source_type=SourceType.HTML_PARSED,
                    ats_type=ATSType.CUSTOM,
                    tags=["remoteok", "api-source", "remote"] + tags_list[:5],
                )
                jobs.append(job)
            except Exception as e:
                logger.warning("Failed to parse RemoteOK job: %s", e)
                continue

        logger.info("RemoteOK: fetched %d jobs", len(jobs))
        return jobs


def fetch_remoteok_jobs(location: str = "", keywords: str = "dev") -> list[Job]:
    """Module-level helper to fetch RemoteOK jobs."""
    fetcher = RemoteOKFetcher()
    return fetcher.fetch_jobs(location=location, keywords=keywords)

