"""
Career Tracker — Matcher Package

Main entry point for job matching. Routes through:
1. TF-IDF cosine similarity (baseline, always runs)
2. LLM judge for borderline scores (Phase 7)
"""

from __future__ import annotations

import logging
from typing import Any

from schema.job import Job, ScoredJob
from matcher.tfidf_matcher import score_jobs, filter_by_score

logger = logging.getLogger(__name__)


def match_jobs(
    jobs: list[Job],
    profile: dict[str, Any],
    threshold_low: float = 0.55,
    threshold_high: float = 0.80,
) -> list[ScoredJob]:
    """
    Match jobs against the user's profile.

    Currently uses TF-IDF scoring only. In Phase 7, borderline scores
    (between threshold_low and threshold_high) will be routed through
    the LLM judge for a more nuanced decision.

    Args:
        jobs: List of Job objects to score
        profile: User profile dict
        threshold_low: Below this = auto-reject
        threshold_high: Above this = auto-match

    Returns:
        List of matched ScoredJob objects (above threshold_low)
    """
    # Step 1: Score all jobs with TF-IDF
    scored = score_jobs(jobs, profile)

    # Step 2: Filter by minimum threshold
    matches = filter_by_score(scored, threshold=threshold_low)

    # Phase 7: for borderline scores (low ≤ score < high),
    # route through LLM judge for a judgment call.
    # For now, all scores above threshold_low are included.

    logger.info(
        "Matching complete: %d/%d jobs matched (threshold=%.2f)",
        len(matches),
        len(jobs),
        threshold_low,
    )

    return matches
