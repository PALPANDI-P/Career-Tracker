"""
Career Tracker — API Sources Package

Free job API integrations for supplementing career page scraping.
Each API source provides a standardized interface for fetching
and converting jobs to the shared Job schema.
"""

from __future__ import annotations

import logging
from typing import Protocol

from schema.job import Job

from fetcher.api_sources.adzuna import AdzunaFetcher, fetch_adzuna_jobs
from fetcher.api_sources.arbeitnow import ArbeitnowFetcher, fetch_arbeitnow_jobs
from fetcher.api_sources.findwork import FindworkFetcher, fetch_findwork_jobs
from fetcher.api_sources.fresher_data_jobs import FresherDataJobsFetcher, fetch_fresher_data_jobs
from fetcher.api_sources.google_jobs import GoogleJobsFetcher, fetch_google_jobs
from fetcher.api_sources.hackernews import HackerNewsFetcher, fetch_hackernews_jobs
from fetcher.api_sources.jobicy import JobicyFetcher, fetch_jobicy_jobs
from fetcher.api_sources.jooble import JoobleFetcher, fetch_jooble_jobs
from fetcher.api_sources.jsearch import JSearchFetcher, fetch_jsearch_jobs
from fetcher.api_sources.linkedin_naukri_fetcher import LinkedInNaukriFetcher, fetch_linkedin_naukri_jobs
from fetcher.api_sources.pan_india_jobs import PanIndiaJobApiFetcher, fetch_pan_india_jobs
from fetcher.api_sources.remoteok import RemoteOKFetcher, fetch_remoteok_jobs
from fetcher.api_sources.remotive import RemotiveFetcher, fetch_remotive_jobs
from fetcher.api_sources.themuse import TheMuseFetcher, fetch_themuse_jobs

logger = logging.getLogger(__name__)


class APISource(Protocol):
    """Protocol for API source fetchers."""

    name: str

    def fetch_jobs(self, location: str = "", keywords: str = "") -> list[Job]:
        """Fetch jobs from this API source."""
        ...


def fetch_all_api_jobs() -> list[Job]:
    """
    Runs all free API job sources and aggregates job listings across India & Global tech hubs.
    """
    all_jobs: list[Job] = []

    sources = [
        PanIndiaJobApiFetcher(),    # Pan-India genuine tech job API (TN, KA, KL, TS, MH, Delhi-NCR)
        LinkedInNaukriFetcher(),    # Genuine LinkedIn & Naukri startup & mid-level company fresher channels
        GoogleJobsFetcher(),        # Google Jobs indexed feeds
        RemotiveFetcher(),          # Remotive open developer jobs API
        JobicyFetcher(),
        RemoteOKFetcher(),
        ArbeitnowFetcher(),
        HackerNewsFetcher(),
        TheMuseFetcher(),
        JoobleFetcher(),
        FindworkFetcher(),
        AdzunaFetcher(),
        JSearchFetcher(),
        FresherDataJobsFetcher(),   # data-role fresher specialist
    ]

    for source in sources:
        try:
            jobs = source.fetch_jobs()
            all_jobs.extend(jobs)
        except Exception as e:
            logger.debug("Fetch failed for source %s: %s", getattr(source, 'name', 'unknown'), e)

    logger.info("Aggregated %d total jobs across all API sources.", len(all_jobs))
    return all_jobs


__all__ = [
    "APISource",
    "AdzunaFetcher",
    "ArbeitnowFetcher",
    "FindworkFetcher",
    "FresherDataJobsFetcher",
    "GoogleJobsFetcher",
    "HackerNewsFetcher",
    "JobicyFetcher",
    "JoobleFetcher",
    "JSearchFetcher",
    "LinkedInNaukriFetcher",
    "PanIndiaJobApiFetcher",
    "RemoteOKFetcher",
    "RemotiveFetcher",
    "TheMuseFetcher",
    "fetch_all_api_jobs",
    "fetch_adzuna_jobs",
    "fetch_arbeitnow_jobs",
    "fetch_findwork_jobs",
    "fetch_fresher_data_jobs",
    "fetch_google_jobs",
    "fetch_hackernews_jobs",
    "fetch_jobicy_jobs",
    "fetch_jooble_jobs",
    "fetch_jsearch_jobs",
    "fetch_linkedin_naukri_jobs",
    "fetch_pan_india_jobs",
    "fetch_remoteok_jobs",
    "fetch_remotive_jobs",
    "fetch_themuse_jobs",
]


