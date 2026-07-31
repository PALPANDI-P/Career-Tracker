"""
Career Tracker — API Pipeline

Fetches jobs from all configured free APIs and converts
them to the shared Job schema. Runs separately from
the career page scraping pipeline (lighter, faster).
"""

from __future__ import annotations

import logging
from pathlib import Path

from config.settings import get_settings
from dedup.store import DedupStore
from filter import detect_job_category, detect_seniority, filter_by_seniority
from matcher import match_jobs
from schema.job import Job, SeniorityLevel

logger = logging.getLogger(__name__)


def _load_api_sources() -> list:
    """Load all available API source fetchers."""
    sources = []

    try:
        from fetcher.api_sources.remoteok import RemoteOKFetcher
        sources.append(RemoteOKFetcher())
    except ImportError:
        logger.debug("RemoteOK fetcher not available")

    try:
        from fetcher.api_sources.arbeitnow import ArbeitnowFetcher
        sources.append(ArbeitnowFetcher())
    except ImportError:
        logger.debug("Arbeitnow fetcher not available")

    try:
        from fetcher.api_sources.adzuna import AdzunaFetcher
        f = AdzunaFetcher()
        if f.is_configured:
            sources.append(f)
    except ImportError:
        logger.debug("Adzuna fetcher not available")

    try:
        from fetcher.api_sources.jsearch import JSearchFetcher
        f = JSearchFetcher()
        if f.is_configured:
            sources.append(f)
    except ImportError:
        logger.debug("JSearch fetcher not available")

    try:
        from fetcher.api_sources.themuse import TheMuseFetcher
        sources.append(TheMuseFetcher())
    except ImportError:
        logger.debug("The Muse fetcher not available")

    try:
        from fetcher.api_sources.hackernews import HackerNewsFetcher
        sources.append(HackerNewsFetcher())
    except ImportError:
        logger.debug("HackerNews fetcher not available")

    try:
        from fetcher.api_sources.jobicy import JobicyFetcher
        sources.append(JobicyFetcher())
    except ImportError:
        logger.debug("Jobicy fetcher not available")

    try:
        from fetcher.api_sources.jooble import JoobleFetcher
        f = JoobleFetcher()
        if f.is_configured:
            sources.append(f)
    except ImportError:
        logger.debug("Jooble fetcher not available")

    try:
        from fetcher.api_sources.findwork import FindworkFetcher
        f = FindworkFetcher()
        if f.is_configured:
            sources.append(f)
    except ImportError:
        logger.debug("Findwork fetcher not available")

    return sources



def run_api_pipeline() -> dict:
    """
    Run the API sources pipeline.

    Fetches from all configured free APIs, merges results,
    applies dedup + filters, scores matches, and pushes
    notifications to the dashboard.

    Returns:
        Summary dict with counts of fetched, new, and matched jobs.
    """
    settings = get_settings()
    store = DedupStore(settings.db_path)
    sources = _load_api_sources()

    if not sources:
        logger.info("No API sources configured. Skipping API pipeline.")
        return {"sources": 0, "fetched": 0, "new": 0, "matched": 0}

    all_jobs: list[Job] = []
    source_errors: list[str] = []

    # ── Fetch from all sources ───────────────────────
    locations = ["tamil nadu", "karnataka", "chennai", "bangalore"]
    keywords_list = [
        "fresher software engineer",
        "junior developer",
        "trainee software",
    ]

    for source in sources:
        source_name = getattr(source, "name", type(source).__name__)
        logger.info("Fetching from API source: %s", source_name)

        try:
            for location in locations:
                for keywords in keywords_list:
                    jobs = source.fetch_jobs(location=location, keywords=keywords)
                    all_jobs.extend(jobs)
        except Exception as e:
            error_msg = f"{source_name}: {e}"
            source_errors.append(error_msg)
            logger.warning("API source %s failed: %s", source_name, e)

    total_fetched = len(all_jobs)
    logger.info("API pipeline: fetched %d total jobs from %d sources", total_fetched, len(sources))

    # ── Dedup ────────────────────────────────────────
    new_jobs = store.filter_new(all_jobs)

    # ── Enrich with fresher detection ────────────────
    for job in new_jobs:
        # Detect seniority
        detected_seniority = detect_seniority(job.title)
        if detected_seniority is not SeniorityLevel.UNKNOWN:
            job.seniority_level = detected_seniority

        # Detect fresher category
        is_fresher, category = detect_job_category(job)
        job.is_fresher_eligible = is_fresher
        job.job_category = category

    # ── Filter by seniority ──────────────────────────
    filtered = filter_by_seniority(new_jobs, settings.target_seniority_levels)

    # ── Match & Score ────────────────────────────────
    import yaml
    with open(settings.profile_path, "r", encoding="utf-8") as fp:
        profile = yaml.safe_load(fp) or {}

    scored = match_jobs(filtered, profile)
    matched = [s for s in scored if s.match_score >= settings.match_threshold_low]

    # ── Push to dashboard notifications ──────────────
    try:
        from dashboard.app import (
            determine_priority,
            push_notification,
            save_notification,
        )

        for scored_job in matched:
            priority = determine_priority(
                scored_job.match_score,
                scored_job.job.is_fresher_eligible,
                scored_job.job.job_category.value,
            )
            scored_job.job.notification_priority = priority

            notification = {
                "type": "new_job",
                "job_id": scored_job.job.id,
                "title": scored_job.job.title,
                "company": scored_job.job.company,
                "location": scored_job.job.location,
                "url": str(scored_job.job.url),
                "match_score": scored_job.match_score,
                "match_reason": scored_job.match_reason,
                "priority": priority,
                "category": scored_job.job.job_category.value,
                "region": scored_job.job.region or "global",
                "city": scored_job.job.city,
                "is_fresher_eligible": scored_job.job.is_fresher_eligible,
            }

            save_notification(settings.db_path, notification)
            push_notification(notification)

    except ImportError:
        logger.debug("Dashboard not available — skipping notification push")
    except Exception as e:
        logger.warning("Failed to push dashboard notifications: %s", e)

    # ── Also send to Telegram & Email ────────────────
    try:
        from notifier import notify_matches
        notify_matches(matched)
        from notifier.email_notifier import send_email_digest
        send_email_digest(matched, settings.email_to)
    except Exception as e:
        logger.warning("Telegram/Email notification failed: %s", e)

    summary = {
        "sources": len(sources),
        "fetched": total_fetched,
        "new": len(new_jobs),
        "filtered": len(filtered),
        "matched": len(matched),
        "errors": source_errors,
    }

    logger.info(
        "API pipeline complete: %d sources, %d fetched, %d new, %d matched",
        summary["sources"],
        summary["fetched"],
        summary["new"],
        summary["matched"],
    )

    return summary
