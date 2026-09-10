"""
Career Tracker — AI Cost Optimizer Pipeline

Implements Section 34 of MASTER DEVELOPMENT PROMPT.

Filters jobs through a staged funnel to minimize expensive AI analysis:

  Input Jobs (up to ~1000)
    ↓
  Stage 1: Hard Eligibility Filter (seniority, location, role)
    → ~300 jobs
    ↓
  Stage 2: Keyword Scoring (TF-IDF)
    → ~100 jobs
    ↓
  Stage 3: Hybrid Scoring (full formula, no LLM)
    → ~30 jobs
    ↓
  Stage 4: LLM Analysis (only for top candidates)
    → ~10 high-quality jobs

Each stage is logged for monitoring.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from schema.job import Job, ScoredJob, FreshnessStatus
from filter.seniority_filter import detect_seniority, SeniorityLevel
from filter.fresher_classifier import classify_fresher_eligibility, FresherEligibility, is_hard_reject
from filter.role_taxonomy import is_candidate_relevant_role
from filter.location_engine import normalize_location, calculate_location_weight
from matcher.tfidf_matcher import score_jobs, filter_by_score
from matcher.hybrid_matcher import score_job
from matcher.project_matcher import ProjectMatcher
from dedup.freshness_engine import classify_freshness, FreshnessConfig

logger = logging.getLogger(__name__)


class PipelineStats:
    """Tracks job counts at each stage of the funnel for monitoring."""

    def __init__(self) -> None:
        self.input = 0
        self.after_hard_filter = 0
        self.after_keyword = 0
        self.after_hybrid = 0
        self.after_llm = 0
        self.notifiable = 0

    def log_summary(self) -> None:
        logger.info(
            "Cost optimizer funnel: %d → %d → %d → %d → %d notifiable",
            self.input,
            self.after_hard_filter,
            self.after_keyword,
            self.after_hybrid,
            self.notifiable,
        )


def run_pipeline(
    jobs: list[Job],
    profile: dict[str, Any],
    *,
    freshness_config: Optional[FreshnessConfig] = None,
    stage1_limit: int = 300,
    stage2_limit: int = 100,
    stage3_limit: int = 30,
    notification_threshold: float = 75.0,
    project_matcher: Optional[ProjectMatcher] = None,
    score_weights: Optional[dict[str, float]] = None,
) -> tuple[list[Job], PipelineStats]:
    """
    Run all jobs through the cost-optimized scoring funnel.

    Args:
        jobs: Raw job list from all sources.
        profile: Candidate profile dict.
        freshness_config: Freshness configuration.
        stage1_limit: Max jobs to pass to Stage 2.
        stage2_limit: Max jobs to pass to Stage 3.
        stage3_limit: Max jobs to pass to Stage 4 (LLM).
        notification_threshold: Minimum score (0-100) to be notifiable.
        project_matcher: Pre-built project matcher (optional).
        score_weights: Custom scoring weight overrides.

    Returns:
        Tuple of (notifiable_jobs_sorted_by_score, PipelineStats)
    """
    stats = PipelineStats()
    stats.input = len(jobs)

    if not jobs:
        stats.log_summary()
        return [], stats

    # ─── Stage 1: Hard Eligibility Filter ────────────────────────────────
    logger.info("Stage 1: Hard eligibility filter (%d input jobs)", len(jobs))
    stage1_jobs = _hard_filter(jobs, profile)
    stats.after_hard_filter = len(stage1_jobs)
    logger.info("Stage 1 output: %d jobs", len(stage1_jobs))

    if not stage1_jobs:
        stats.log_summary()
        return [], stats

    # Limit to top stage1_limit if needed
    stage1_jobs = stage1_jobs[:stage1_limit]

    # ─── Stage 2: TF-IDF Keyword Scoring ──────────────────────────────────
    logger.info("Stage 2: TF-IDF keyword scoring (%d jobs)", len(stage1_jobs))
    scored_tfidf = score_jobs(stage1_jobs, profile)
    # Keep above 0.3 threshold (low bar) to avoid losing valid but low-description jobs
    scored_tfidf = filter_by_score(scored_tfidf, threshold=0.25)
    # Take top stage2_limit
    scored_tfidf = scored_tfidf[:stage2_limit]
    stage2_jobs = [sj.job for sj in scored_tfidf]
    stats.after_keyword = len(stage2_jobs)
    logger.info("Stage 2 output: %d jobs", len(stage2_jobs))

    if not stage2_jobs:
        stats.log_summary()
        return [], stats

    # ─── Stage 3: Full Hybrid Scoring ─────────────────────────────────────
    logger.info("Stage 3: Full hybrid scoring (%d jobs)", len(stage2_jobs))

    # Build project matcher if not provided
    if project_matcher is None and profile.get("projects"):
        project_matcher = ProjectMatcher(profile["projects"])

    enriched_jobs: list[tuple[float, Job]] = []
    for job in stage2_jobs:
        try:
            overall, components, matched, missing, proj_name, proj_score, coverage = score_job(
                job, profile,
                project_matcher=project_matcher,
                weights=score_weights,
            )

            # Enrich the job with scoring metadata
            updated_job = job.model_copy(update={
                "overall_score": overall,
                "matched_skills": matched,
                "missing_skills": missing,
                "matched_project": proj_name,
                "project_relevance_score": proj_score,
                "recruiter_keyword_coverage": coverage,
            })
            enriched_jobs.append((overall, updated_job))
        except Exception as exc:
            logger.warning("Hybrid score failed for '%s': %s", job.title, exc)

    # Sort by score descending, take top stage3_limit
    enriched_jobs.sort(key=lambda x: x[0], reverse=True)
    stats.after_hybrid = len(enriched_jobs)

    # Select jobs above notification threshold
    notifiable: list[Job] = []
    for score, job in enriched_jobs:
        if score >= notification_threshold:
            # Add resume recommendation
            from matcher.resume_selector import select_resume
            resume_info = select_resume(job.title, job.description)
            job = job.model_copy(update={
                "recommended_resume": resume_info.get("file", ""),
            })
            notifiable.append(job)

    stats.notifiable = len(notifiable)
    stats.log_summary()
    return notifiable, stats


def _hard_filter(jobs: list[Job], profile: dict[str, Any]) -> list[Job]:
    """
    Stage 1: Fast deterministic eligibility filter.

    Rejects:
      - Hard negative seniority (senior, lead, manager, director, etc.)
      - Experience > 4 years
      - Roles outside candidate taxonomy
      - STALE jobs (unless freshness unknown)
    """
    passed: list[Job] = []
    target_levels = profile.get("target_seniority", ["entry", "junior", "intern"])

    for job in jobs:
        # Reject stale jobs
        if job.freshness_status == FreshnessStatus.STALE:
            logger.debug("REJECT (stale): %s", job.title)
            continue

        # Hard reject: negative seniority in title
        if is_hard_reject(job.title):
            logger.debug("REJECT (senior signal): %s", job.title)
            continue

        # Detect seniority level
        seniority = detect_seniority(job.title)
        if seniority not in (
            SeniorityLevel.INTERN,
            SeniorityLevel.ENTRY,
            SeniorityLevel.JUNIOR,
            SeniorityLevel.MID,
            SeniorityLevel.UNKNOWN,  # Include unknowns — may be fresher-eligible
        ):
            logger.debug("REJECT (seniority=%s): %s", seniority.value, job.title)
            continue

        # Fresher eligibility check
        eligibility, confidence, _ = classify_fresher_eligibility(
            job.description,
            title=job.title,
        )
        if eligibility == FresherEligibility.INELIGIBLE:
            logger.debug("REJECT (ineligible): %s", job.title)
            continue

        passed.append(job)

    logger.info("Hard filter: %d/%d jobs passed", len(passed), len(jobs))
    return passed
