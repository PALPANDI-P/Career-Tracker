"""
Career Tracker — Freshness Engine

Implements Section 6 of MASTER DEVELOPMENT PROMPT.

Determines whether a job is genuinely fresh (posted within the configured
max_age_hours window) using a priority chain of available timestamps.

Priority chain (highest → lowest):
  1. published_at  — official ATS publish timestamp
  2. updated_at    — official ATS last-updated (only if allow_updated_jobs=True)
  3. posted_date   — backwards-compat alias for published_at
  4. first_seen_at — when OUR system first discovered the job

Freshness classifications:
  FRESH_CONFIRMED   — official published_at within threshold
  UPDATED_CONFIRMED — official updated_at within threshold
  FIRST_SEEN        — newly discovered, no official publish date (configurable)
  STALE             — older than threshold
  UNKNOWN           — no reliable timestamp available
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from schema.job import Job, FreshnessStatus

logger = logging.getLogger(__name__)


class FreshnessConfig:
    """Configuration for freshness evaluation."""

    def __init__(
        self,
        max_age_hours: float = 24.0,
        allow_updated_jobs: bool = True,
        allow_first_seen_without_publish_date: bool = False,
    ) -> None:
        self.max_age_hours = max_age_hours
        self.allow_updated_jobs = allow_updated_jobs
        self.allow_first_seen_without_publish_date = allow_first_seen_without_publish_date


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _age_hours(ts: datetime) -> float:
    """Return hours since the given timestamp."""
    now = _now_utc()
    # Ensure timezone-aware comparison
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = now - ts
    return delta.total_seconds() / 3600.0


def classify_freshness(
    job: Job,
    config: Optional[FreshnessConfig] = None,
) -> FreshnessStatus:
    """
    Classify a job's freshness using the priority timestamp chain.

    Never falsely claims a job is "posted today" unless the source
    provides sufficient evidence.

    Args:
        job: Job to evaluate.
        config: Freshness configuration (uses defaults if None).

    Returns:
        FreshnessStatus enum value.
    """
    if config is None:
        config = FreshnessConfig()

    threshold = config.max_age_hours

    # Priority 1: Official published_at (or its alias posted_date)
    pub_ts = job.published_at or job.posted_date
    if pub_ts is not None:
        age = _age_hours(pub_ts)
        if age <= threshold:
            logger.debug(
                "Job '%s' is FRESH_CONFIRMED: published %.1f hours ago",
                job.title,
                age,
            )
            return FreshnessStatus.FRESH_CONFIRMED
        else:
            logger.debug(
                "Job '%s' is STALE: published %.1f hours ago (threshold: %.0f)",
                job.title,
                age,
                threshold,
            )
            return FreshnessStatus.STALE

    # Priority 2: Official updated_at (only if configured)
    if config.allow_updated_jobs and job.updated_at is not None:
        age = _age_hours(job.updated_at)
        if age <= threshold:
            logger.debug(
                "Job '%s' is UPDATED_CONFIRMED: updated %.1f hours ago",
                job.title,
                age,
            )
            return FreshnessStatus.UPDATED_CONFIRMED
        else:
            return FreshnessStatus.STALE

    # Priority 3: first_seen_at (newly discovered in this run)
    if job.first_seen_at is not None:
        if config.allow_first_seen_without_publish_date:
            age = _age_hours(job.first_seen_at)
            if age <= threshold:
                logger.debug(
                    "Job '%s' is FIRST_SEEN: first discovered %.1f hours ago",
                    job.title,
                    age,
                )
                return FreshnessStatus.FIRST_SEEN
            else:
                return FreshnessStatus.STALE
        else:
            # We can't confirm freshness without an official publish date
            logger.debug(
                "Job '%s': UNKNOWN freshness — only first_seen_at available, no official publish date",
                job.title,
            )
            return FreshnessStatus.UNKNOWN

    # No usable timestamp at all
    logger.debug("Job '%s': UNKNOWN freshness — no timestamps available", job.title)
    return FreshnessStatus.UNKNOWN


def is_notifiable(
    freshness_status: FreshnessStatus,
    config: Optional[FreshnessConfig] = None,
) -> bool:
    """
    Returns True if this job should trigger a notification based on freshness.

    Default rule: FRESH_CONFIRMED or UPDATED_CONFIRMED qualifies.
    FIRST_SEEN qualifies only if allow_first_seen_without_publish_date is True.
    """
    if config is None:
        config = FreshnessConfig()

    if freshness_status == FreshnessStatus.FRESH_CONFIRMED:
        return True
    if freshness_status == FreshnessStatus.UPDATED_CONFIRMED and config.allow_updated_jobs:
        return True
    if freshness_status == FreshnessStatus.FIRST_SEEN and config.allow_first_seen_without_publish_date:
        return True
    return False


def classify_and_update(
    job: Job,
    config: Optional[FreshnessConfig] = None,
    mark_first_seen: bool = True,
) -> Job:
    """
    Classify freshness and update the job object in place.

    Args:
        job: Job to evaluate and update.
        config: Freshness configuration.
        mark_first_seen: If True and first_seen_at is unset, set it to now.

    Returns:
        Updated Job (with freshness_status set).
    """
    if mark_first_seen and job.first_seen_at is None:
        job = job.model_copy(update={"first_seen_at": _now_utc()})

    freshness = classify_freshness(job, config)
    return job.model_copy(update={"freshness_status": freshness})
