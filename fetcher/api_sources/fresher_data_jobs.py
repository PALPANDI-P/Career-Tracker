"""
Career Tracker — Fresher Data Jobs API Fetcher

Specialised fetcher that queries existing free API integrations (JSearch,
Adzuna) with data-role specific keywords targeting entry-level/fresher
openings in India.

Role keywords covered:
  • Data Analyst Fresher
  • Data Engineer Trainee
  • Business Analyst Fresher
  • Business Intelligence Analyst (Entry)
  • Data Science Trainee / Associate
  • ETL Developer Fresher
  • SQL Developer (0-1 yrs)

Results are classified with:
  • is_fresher_eligible = True
  • job_category = JobCategory.FRESHER
  • tags = ["data-role", "fresher", <source>]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from config.settings import get_settings
from schema.job import ATSType, Job, JobCategory, SeniorityLevel, SourceType

logger = logging.getLogger(__name__)

# ── Search Query Sets ────────────────────────────────────────────────────────

# Keywords used in API searches — kept broad enough for API free-tier budgets
DATA_FRESHER_KEYWORDS: list[str] = [
    "data analyst fresher",
    "data engineer trainee",
    "business analyst fresher",
    "data science trainee",
    "junior data analyst",
    "ETL developer fresher",
    "SQL developer 0 1 years",
    "business intelligence analyst entry level",
    "associate data engineer india",
    "ML engineer fresher india",
]

# India locations for scoped searches
INDIA_LOCATIONS: list[str] = [
    "Chennai",
    "Bangalore",
    "Hyderabad",
    "Remote India",
]

# Title keywords that signal a fresher/entry role
FRESHER_TITLE_SIGNALS: set[str] = {
    "fresher",
    "trainee",
    "trainee",
    "junior",
    "associate",
    "entry",
    "graduate",
    "new grad",
    "0-1",
    "0 to 1",
    "intern",
}

# Title/description keywords that confirm this is a data role
DATA_ROLE_SIGNALS: set[str] = {
    "data analyst",
    "data engineer",
    "data scientist",
    "data science",
    "business analyst",
    "business intelligence",
    "bi analyst",
    "bi developer",
    "etl",
    "sql developer",
    "analytics engineer",
    "ml engineer",
    "machine learning",
    "data pipeline",
    "tableau",
    "power bi",
    "looker",
    "warehouse",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_fresher_eligible(title: str, description: str) -> bool:
    """Return True if job text contains fresher-eligibility signals."""
    combined = (title + " " + description).lower()
    return any(sig in combined for sig in FRESHER_TITLE_SIGNALS)


def _is_data_role(title: str, description: str) -> bool:
    """Return True if job is in the data domain."""
    combined = (title + " " + description).lower()
    return any(sig in combined for sig in DATA_ROLE_SIGNALS)


def _detect_seniority(title: str) -> SeniorityLevel:
    """Coarse seniority classification from title text."""
    t = title.lower()
    if any(w in t for w in ("intern", "internship")):
        return SeniorityLevel.INTERN
    if any(w in t for w in ("trainee", "fresher", "graduate", "new grad")):
        return SeniorityLevel.ENTRY
    if any(w in t for w in ("junior", "associate", "jr.", "entry")):
        return SeniorityLevel.JUNIOR
    return SeniorityLevel.ENTRY  # default for this fetcher


# ── JSearch Fetcher ──────────────────────────────────────────────────────────


class FresherDataJobsJSearchFetcher:
    """
    Query JSearch (RapidAPI) for data-role fresher openings in India.

    Free tier: 100 requests/month. Uses existing CT_JSEARCH_API_KEY from .env.
    API docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
    """

    name = "jsearch_data_fresher"
    BASE_URL = "https://jsearch.p.rapidapi.com/search"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = getattr(settings, "jsearch_api_key", None)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch_jobs(
        self,
        keywords: list[str] | None = None,
        country: str = "in",
        num_pages: int = 1,
        date_posted: str = "week",
    ) -> list[Job]:
        """
        Fetch data-role fresher jobs from JSearch.

        Args:
            keywords: Override the default DATA_FRESHER_KEYWORDS list.
            country: ISO country code ('in' for India).
            num_pages: Number of result pages per keyword (1 page ≈ 10 results).
            date_posted: 'today', 'week', 'month', or 'all'.

        Returns:
            Deduplicated list of Job objects tagged as data-role fresher.
        """
        if not self.is_configured:
            logger.warning("JSearch API key not configured — skipping data fresher fetch.")
            return []

        search_keywords = keywords or DATA_FRESHER_KEYWORDS
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }

        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        # Limit to first 3 keywords to conserve free-tier quota
        for kw in search_keywords[:3]:
            params: dict[str, Any] = {
                "query": f"{kw} India",
                "country": country,
                "num_pages": num_pages,
                "date_posted": date_posted,
            }
            try:
                resp = requests.get(
                    self.BASE_URL,
                    headers=headers,
                    params=params,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                logger.error("JSearch data-fresher request failed for '%s': %s", kw, exc)
                continue
            except ValueError:
                logger.error("JSearch returned invalid JSON for '%s'", kw)
                continue

            for result in data.get("data", []):
                job = self._parse_result(result)
                if job and job.id not in seen_ids:
                    seen_ids.add(job.id)
                    all_jobs.append(job)

        logger.info(
            "JSearch data-fresher: collected %d unique data-role fresher jobs.",
            len(all_jobs),
        )
        return all_jobs

    def _parse_result(self, result: dict[str, Any]) -> Job | None:
        """Convert a JSearch result dict to a Job object."""
        try:
            title = result.get("job_title", "Untitled")
            description = result.get("job_description", "")
            company = result.get("employer_name", "Unknown")
            location = (
                result.get("job_city", "")
                or result.get("job_state", "")
                or result.get("job_country", "India")
            )
            url = result.get("job_apply_link") or result.get("job_google_link", "")
            ext_id = result.get("job_id", "")

            if not url:
                return None

            # Skip if not a data role
            if not _is_data_role(title, description):
                return None

            job = Job(
                id=Job.make_id("jsearch", ext_id),
                external_id=ext_id,
                title=title,
                company=company,
                location=location,
                url=url,
                description=description,
                source_type=SourceType.HTML_PARSED,
                ats_type=ATSType.CUSTOM,
                seniority_level=_detect_seniority(title),
                is_fresher_eligible=_is_fresher_eligible(title, description),
                job_category=JobCategory.FRESHER,
                region="india",
                experience_required="0-2 years",
                tags=["data-role", "fresher", "jsearch", "api-source"],
            )
            return job
        except Exception as exc:
            logger.warning("Failed to parse JSearch data-fresher result: %s", exc)
            return None


# ── Adzuna Fetcher ───────────────────────────────────────────────────────────


class FresherDataJobsAdzunaFetcher:
    """
    Query Adzuna India API for data-role fresher openings.

    Free tier: 100 requests/day. Uses existing CT_ADZUNA_* keys from .env.
    API docs: https://developer.adzuna.com/
    """

    name = "adzuna_data_fresher"
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search"

    def __init__(self) -> None:
        settings = get_settings()
        self.app_id = getattr(settings, "adzuna_app_id", None)
        self.api_key = getattr(settings, "adzuna_api_key", None)

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.api_key)

    def fetch_jobs(
        self,
        keywords: list[str] | None = None,
        locations: list[str] | None = None,
        results_per_page: int = 20,
        max_days_old: int = 14,
    ) -> list[Job]:
        """
        Fetch data-role fresher jobs from Adzuna India.

        Args:
            keywords: Search query strings (uses DATA_FRESHER_KEYWORDS[:2] by default).
            locations: Indian city names (uses INDIA_LOCATIONS[:2] by default).
            results_per_page: Number of results per API call.
            max_days_old: Only return jobs posted within this many days.

        Returns:
            List of Job objects for data-role fresher openings.
        """
        if not self.is_configured:
            logger.warning("Adzuna API keys not configured — skipping data fresher fetch.")
            return []

        search_keywords = (keywords or DATA_FRESHER_KEYWORDS)[:2]
        search_locations = (locations or INDIA_LOCATIONS)[:2]

        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        for kw in search_keywords:
            for loc in search_locations:
                url = f"{self.BASE_URL}/1"
                params: dict[str, Any] = {
                    "app_id": self.app_id,
                    "app_key": self.api_key,
                    "what": kw,
                    "where": loc,
                    "max_days_old": max_days_old,
                    "results_per_page": results_per_page,
                    "sort_by": "date",
                    "content-type": "application/json",
                }
                try:
                    resp = requests.get(url, params=params, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                except requests.RequestException as exc:
                    logger.error(
                        "Adzuna data-fresher request failed ('%s' / '%s'): %s",
                        kw,
                        loc,
                        exc,
                    )
                    continue
                except ValueError:
                    logger.error("Adzuna returned invalid JSON for '%s'", kw)
                    continue

                for result in data.get("results", []):
                    job = self._parse_result(result, loc)
                    if job and job.id not in seen_ids:
                        seen_ids.add(job.id)
                        all_jobs.append(job)

        logger.info(
            "Adzuna data-fresher: collected %d unique data-role fresher jobs.",
            len(all_jobs),
        )
        return all_jobs

    def _parse_result(self, result: dict[str, Any], fallback_location: str) -> Job | None:
        """Convert an Adzuna result dict to a Job object."""
        try:
            title = result.get("title", "Untitled")
            description = result.get("description", "")
            company = result.get("company", {}).get("display_name", "Unknown")
            location = result.get("location", {}).get("display_name", fallback_location)
            url = result.get("redirect_url", "")
            ext_id = str(result.get("id", ""))

            if not url or not ext_id:
                return None

            # Skip if not a data role or not fresher-eligible
            if not _is_data_role(title, description):
                return None

            job = Job(
                id=Job.make_id("adzuna", ext_id),
                external_id=ext_id,
                title=title,
                company=company,
                location=location,
                url=url,
                description=description,
                source_type=SourceType.HTML_PARSED,
                ats_type=ATSType.CUSTOM,
                seniority_level=_detect_seniority(title),
                is_fresher_eligible=_is_fresher_eligible(title, description),
                job_category=JobCategory.FRESHER,
                region="india",
                experience_required="0-2 years",
                tags=["data-role", "fresher", "adzuna", "api-source"],
            )
            return job
        except Exception as exc:
            logger.warning("Failed to parse Adzuna data-fresher result: %s", exc)
            return None


# ── Composite Fetcher ─────────────────────────────────────────────────────────


class FresherDataJobsFetcher:
    """
    Composite fetcher: aggregates data-role fresher jobs from JSearch + Adzuna.

    This is the single entry point used in fetch_all_api_jobs().
    """

    name = "fresher_data_jobs"

    def __init__(self) -> None:
        self._jsearch = FresherDataJobsJSearchFetcher()
        self._adzuna = FresherDataJobsAdzunaFetcher()

    def fetch_jobs(
        self,
        location: str = "India",
        keywords: str = "data fresher",
    ) -> list[Job]:
        """
        Fetch and merge data-role fresher jobs from all configured sources.

        Args:
            location: Ignored (uses built-in India scope). Kept for protocol compat.
            keywords: Ignored (uses DATA_FRESHER_KEYWORDS). Kept for protocol compat.

        Returns:
            Deduplicated list of data-role fresher Job objects.
        """
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        for fetcher in (self._jsearch, self._adzuna):
            try:
                jobs = fetcher.fetch_jobs()
                for job in jobs:
                    if job.id not in seen_ids:
                        seen_ids.add(job.id)
                        all_jobs.append(job)
            except Exception as exc:
                logger.error(
                    "FresherDataJobsFetcher: source '%s' failed: %s",
                    fetcher.name,
                    exc,
                )

        logger.info(
            "FresherDataJobsFetcher: %d total unique data-role fresher jobs aggregated.",
            len(all_jobs),
        )
        return all_jobs


# ── Module-level Helper ───────────────────────────────────────────────────────


def fetch_fresher_data_jobs(
    location: str = "India",
    keywords: str = "data fresher",
) -> list[Job]:
    """
    Module-level helper — fetch all data-role fresher jobs.

    Usage:
        from fetcher.api_sources.fresher_data_jobs import fetch_fresher_data_jobs
        jobs = fetch_fresher_data_jobs()
    """
    return FresherDataJobsFetcher().fetch_jobs(location=location, keywords=keywords)
