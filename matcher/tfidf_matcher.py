"""
Career Tracker — TF-IDF Matcher

Scores jobs against the user's profile using TF-IDF cosine similarity.
This is the cheap, fast, deterministic baseline — no LLM calls.

Jobs scoring above the high threshold are automatic matches.
Jobs scoring below the low threshold are automatic rejects.
Jobs in the borderline range (55–80% by default) will be routed
to the LLM judge in Phase 7.
"""

from __future__ import annotations

import logging
from typing import Any

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from schema.job import Job, ScoredJob

logger = logging.getLogger(__name__)


def load_profile(profile_path: str) -> dict[str, Any]:
    """Load user profile from YAML file."""
    with open(profile_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_profile_text(profile: dict[str, Any]) -> str:
    """
    Build a single text document from the user's profile.

    Combines target titles, skills, boost keywords, and summary
    into a single string for TF-IDF comparison against job descriptions.
    """
    parts: list[str] = []

    titles = profile.get("target_titles", [])
    parts.extend(titles * 3)  # Triple-weight titles

    skills = profile.get("skills", [])
    parts.extend(skills * 2)  # Double-weight skills

    boost = profile.get("boost_keywords", [])
    parts.extend(boost)

    summary = profile.get("summary", "")
    if summary:
        parts.append(summary)

    return " ".join(parts)


def _build_job_text(job: Job) -> str:
    """Build a single text document from a job for TF-IDF comparison."""
    parts = [
        job.title,
        job.title,  # Double-weight title
        job.description,
    ]
    if job.department:
        parts.append(job.department)
    if job.location:
        parts.append(job.location)

    return " ".join(parts)


def _apply_keyword_adjustments(
    score: float,
    job: Job,
    profile: dict[str, Any],
) -> float:
    """
    Adjust TF-IDF score based on boost/penalize keywords.

    Each boost keyword match adds +0.05, each penalize match subtracts -0.10.
    Final score clamped to [0, 1].
    """
    job_text_lower = f"{job.title} {job.description}".lower()

    adjustment = 0.0

    for keyword in profile.get("boost_keywords", []):
        if keyword.lower() in job_text_lower:
            adjustment += 0.05

    for keyword in profile.get("penalize_keywords", []):
        if keyword.lower() in job_text_lower:
            adjustment -= 0.10

    return max(0.0, min(1.0, score + adjustment))


def score_jobs(
    jobs: list[Job],
    profile: dict[str, Any],
) -> list[ScoredJob]:
    """
    Score jobs against the user's profile using TF-IDF cosine similarity.

    Returns ScoredJob objects sorted by score (highest first).
    """
    if not jobs:
        return []

    profile_text = _build_profile_text(profile)
    job_texts = [_build_job_text(job) for job in jobs]

    # First document = profile, rest = jobs
    all_texts = [profile_text] + job_texts

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=5000,
        ngram_range=(1, 2),  # Unigrams + bigrams
    )

    tfidf_matrix = vectorizer.fit_transform(all_texts)

    profile_vector = tfidf_matrix[0:1]
    job_vectors = tfidf_matrix[1:]
    similarities = cosine_similarity(profile_vector, job_vectors).flatten()

    scored_jobs: list[ScoredJob] = []

    for job, raw_score in zip(jobs, similarities):
        adjusted_score = _apply_keyword_adjustments(float(raw_score), job, profile)
        reason = _build_match_reason(job, profile, adjusted_score)

        scored_jobs.append(
            ScoredJob(
                job=job,
                match_score=round(adjusted_score, 4),
                match_reason=reason,
            )
        )

    scored_jobs.sort(key=lambda sj: sj.match_score, reverse=True)

    logger.info(
        "Scored %d jobs: top=%.2f, bottom=%.2f",
        len(scored_jobs),
        scored_jobs[0].match_score if scored_jobs else 0,
        scored_jobs[-1].match_score if scored_jobs else 0,
    )

    return scored_jobs


def _build_match_reason(job: Job, profile: dict[str, Any], score: float) -> str:
    """Build a human-readable reason for the match score."""
    job_text_lower = f"{job.title} {job.description}".lower()
    matching_skills = [
        skill for skill in profile.get("skills", [])
        if skill.lower() in job_text_lower
    ]

    if matching_skills:
        skills_str = ", ".join(matching_skills[:5])
        return f"Score {score:.0%} — matching skills: {skills_str}"
    return f"Score {score:.0%} — general keyword overlap"


def filter_by_score(
    scored_jobs: list[ScoredJob],
    threshold: float = 0.55,
) -> list[ScoredJob]:
    """Filter scored jobs to only those above the threshold."""
    kept = [sj for sj in scored_jobs if sj.match_score >= threshold]
    logger.info(
        "Score filter: %d/%d jobs above threshold %.2f",
        len(kept), len(scored_jobs), threshold,
    )
    return kept
