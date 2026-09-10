"""
Career Tracker — Hybrid Matcher

Implements Sections 13, 14, 15, and 43 of MASTER DEVELOPMENT PROMPT.

Hybrid scoring formula:
  overall_score =
      role_score      * 0.25
    + skill_score     * 0.25
    + experience_score* 0.15
    + education_score * 0.10
    + location_score  * 0.10
    + project_score   * 0.10
    + freshness_score * 0.05

Skill breakdown per Section 14:
  must_have, nice_to_have, candidate_has, candidate_missing

Recruiter keyword coverage per Section 43.

All weights are configurable.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from schema.job import Job, ScoredJob, FreshnessStatus
from filter.fresher_classifier import classify_fresher_eligibility, FresherEligibility
from filter.location_engine import normalize_location, calculate_location_weight
from filter.role_taxonomy import classify_role, TaxonomyCategory
from matcher.project_matcher import ProjectMatcher
from matcher.resume_selector import select_resume

logger = logging.getLogger(__name__)

# ─── Default Score Weights (Section 13) ──────────────────────────────
DEFAULT_WEIGHTS: dict[str, float] = {
    "role_score": 0.25,
    "skill_score": 0.25,
    "experience_score": 0.15,
    "education_score": 0.10,
    "location_score": 0.10,
    "project_score": 0.10,
    "freshness_score": 0.05,
}

# ─── Notification Threshold (Section 22) ─────────────────────────────
NOTIFICATION_THRESHOLD = 75.0  # Minimum score to notify candidate
HIGH_PRIORITY_THRESHOLD = 90.0  # Score for 🔥 HIGH PRIORITY badge
STRONG_MATCH_THRESHOLD = 80.0   # Score for 🟢 STRONG MATCH badge
REVIEW_THRESHOLD = 70.0         # Score for 🟡 REVIEW badge


def _skill_score(
    job_text: str,
    candidate_skills: list[str],
) -> tuple[float, list[str], list[str]]:
    """
    Calculate skill match score (0–100) and return matched/missing skills.

    Separates must_have from nice_to_have implicitly:
    Skills found in title are weighted higher (must-have signal).

    Returns:
        (score, matched_skills, missing_skills)
    """
    job_lower = job_text.lower()
    matched: list[str] = []
    missing: list[str] = []

    for skill in candidate_skills:
        # Flexible match: handle "REST APIs" ≈ "RESTful API" ≈ "REST API"
        skill_lower = skill.lower().replace("/", " ").replace("-", " ")
        skill_words = skill_lower.split()

        # Check if any word form of the skill appears in the job text
        found = any(
            re.search(r'\b' + re.escape(word) + r'\b', job_lower)
            for word in skill_words
            if len(word) >= 3  # Skip very short tokens
        )
        if found:
            matched.append(skill)
        else:
            missing.append(skill)

    if not candidate_skills:
        return 0.0, [], []

    score = (len(matched) / len(candidate_skills)) * 100.0
    return round(score, 1), matched, missing


def _experience_score(
    job: Job,
    experience_years: int = 0,
) -> float:
    """
    Score experience match.

    Freshers (0 years) score 100 on 0-1 year roles,
    penalized for 2+ year requirements.
    """
    text = f"{job.experience_text or ''} {job.description[:300]}".lower()

    # Strongly fresher-eligible patterns -> 100
    if re.search(r'\b0\s*[-–]\s*1\s+year[s]?\b|\bfresher\b|\btrainee\b|\b0\s+year[s]?\b', text):
        return 100.0

    # Up to 2 years -> 80
    if re.search(r'\b0\s*[-–]\s*2\s+year[s]?\b|\b[12]\s+year[s]?\s+(?:preferred|experience)?\b', text):
        return 80.0

    # 2-3 years -> 50 (lower priority but not impossible)
    if re.search(r'\b[23]\s*[-–]\s*4\s+year[s]?\b', text):
        return 50.0

    # 3+ year requirement -> 20
    if re.search(r'\b[345]\+?\s+year[s]?\b', text):
        return 20.0

    # 5+ years -> 0
    if re.search(r'\b[5-9]\+?\s+year[s]?\b|\b1[0-9]\+?\s+year[s]?\b', text):
        return 0.0

    # No experience requirement stated -> neutral 70
    return 70.0


def _education_score(job: Job) -> float:
    """
    Score education match for MCA/BCA candidate.

    Full match if job mentions MCA, BCA, B.E, B.Tech, MSc or equivalent.
    """
    text = f"{job.education_text or ''} {job.description[:500]}".lower()

    # Perfect match signals
    if re.search(r'\bmca\b|\bmaster\s+of\s+computer\s+applications?\b', text):
        return 100.0
    if re.search(r'\bbca\b|\bbachelor\s+of\s+computer\s+applications?\b', text):
        return 100.0
    if re.search(r'\bb\.?e\.?\b|\bb\.?tech\b|\bcomputer\s+science\b|\bcs\b|\bit\b', text):
        return 95.0
    if re.search(r'\bm\.?sc\b|\bm\.?tech\b|\bpg\b|\bpost\s*grad', text):
        return 90.0
    if re.search(r'\bbachelor[\'s]?\b|\bdegree\b|\bgraduate\b', text):
        return 85.0

    # No education requirement stated -> neutral
    return 80.0


def _freshness_score(job: Job) -> float:
    """Score freshness (Section 6). FRESH_CONFIRMED = 100, STALE = 0."""
    if job.freshness_status == FreshnessStatus.FRESH_CONFIRMED:
        return 100.0
    if job.freshness_status == FreshnessStatus.UPDATED_CONFIRMED:
        return 90.0
    if job.freshness_status == FreshnessStatus.FIRST_SEEN:
        return 70.0
    if job.freshness_status == FreshnessStatus.STALE:
        return 0.0
    return 50.0  # UNKNOWN


def _role_score(job: Job, candidate_taxonomy: Optional[list[str]] = None) -> float:
    """Score role taxonomy alignment (Section 12)."""
    category, subcategory, confidence = classify_role(job.title, job.description)

    target = candidate_taxonomy or [
        TaxonomyCategory.SOFTWARE_DEVELOPMENT.value,
        TaxonomyCategory.AI_ML.value,
        TaxonomyCategory.DATA.value,
        TaxonomyCategory.TESTING.value,
    ]

    if category.value not in target:
        return 20.0  # Unrelated category penalty

    return round(confidence * 100.0, 1)


def _recruiter_keyword_coverage(
    job: Job,
    candidate_skills: list[str],
    candidate_titles: list[str],
) -> float:
    """
    Calculate recruiter keyword reachability score (Section 43).

    Measures how well the candidate's existing resume/profile naturally
    aligns with keywords a recruiter would search for this job.
    """
    job_text = f"{job.title} {job.description[:1000]}".lower()
    candidate_keywords = [
        *[t.lower() for t in candidate_titles],
        *[s.lower() for s in candidate_skills],
    ]

    # Extract meaningful words from job text
    job_words = set(re.findall(r'\b[a-z][a-z0-9\+#]{2,}\b', job_text))
    candidate_words = set()
    for kw in candidate_keywords:
        candidate_words.update(kw.lower().split())

    overlap = len(job_words & candidate_words)
    if not job_words:
        return 0.0

    coverage = (overlap / len(job_words)) * 100.0
    return round(min(coverage * 2.0, 100.0), 1)  # Scale up to be more meaningful


def score_job(
    job: Job,
    profile: dict[str, Any],
    project_matcher: Optional[ProjectMatcher] = None,
    weights: Optional[dict[str, float]] = None,
) -> tuple[float, dict[str, float], list[str], list[str], Optional[str], float, float]:
    """
    Calculate the full hybrid score for a single job.

    Args:
        job: Job to evaluate.
        profile: Candidate profile dict (from profile.yaml).
        project_matcher: Pre-built ProjectMatcher instance.
        weights: Custom weight overrides.

    Returns:
        Tuple of:
          overall_score (0-100),
          component_scores dict,
          matched_skills list,
          missing_skills list,
          recommended_resume filename,
          project_relevance_score (0-100),
          recruiter_keyword_coverage (0-100)
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    candidate_skills: list[str] = profile.get("skills", [])
    candidate_titles: list[str] = profile.get("target_titles", [])
    location_weights = profile.get("location_weights", {})
    priority_cities = profile.get("priority_cities", [])
    preferred_states = profile.get("preferred_states", [])

    job_text = f"{job.title} {job.description}"

    # Component scores
    role_s = _role_score(job)
    skill_s, matched_skills, missing_skills = _skill_score(job_text, candidate_skills)
    exp_s = _experience_score(job, profile.get("experience_years", 0))
    edu_s = _education_score(job)
    fresh_s = _freshness_score(job)

    # Location score
    loc = normalize_location(job.canonical_location or job.location)
    location_s = calculate_location_weight(
        loc,
        priority_cities=priority_cities,
        preferred_states=preferred_states,
        location_weights=location_weights,
    ) * 100.0

    # Project score
    project_name = None
    project_s = 0.0
    if project_matcher:
        project_name, project_raw = project_matcher.find_best_match(job.title, job.description)
        project_s = project_raw
    elif profile.get("projects"):
        pm = ProjectMatcher(profile["projects"])
        project_name, project_raw = pm.find_best_match(job.title, job.description)
        project_s = project_raw

    # Recruiter keyword coverage
    recruiter_coverage = _recruiter_keyword_coverage(job, candidate_skills, candidate_titles)

    # Weighted overall score
    overall = (
        role_s * w["role_score"]
        + skill_s * w["skill_score"]
        + exp_s * w["experience_score"]
        + edu_s * w["education_score"]
        + location_s * w["location_score"]
        + project_s * w["project_score"]
        + fresh_s * w["freshness_score"]
    )

    component_scores = {
        "role_score": round(role_s, 1),
        "skill_score": round(skill_s, 1),
        "experience_score": round(exp_s, 1),
        "education_score": round(edu_s, 1),
        "location_score": round(location_s, 1),
        "project_score": round(project_s, 1),
        "freshness_score": round(fresh_s, 1),
        "overall": round(overall, 1),
    }

    # Resume selection
    resume_info = select_resume(job.title, job.description)
    recommended_resume = resume_info.get("file", "")

    logger.debug(
        "Hybrid score for '%s': %.1f (role=%.0f, skill=%.0f, exp=%.0f, loc=%.0f, proj=%.0f)",
        job.title,
        overall,
        role_s, skill_s, exp_s, location_s, project_s,
    )

    return (
        round(overall, 1),
        component_scores,
        matched_skills,
        missing_skills,
        project_name,
        project_s,
        recruiter_coverage,
    )


def get_notification_badge(score: float) -> str:
    """Return emoji badge for notification priority (Section 22)."""
    if score >= HIGH_PRIORITY_THRESHOLD:
        return "🔥"
    if score >= STRONG_MATCH_THRESHOLD:
        return "🟢"
    if score >= REVIEW_THRESHOLD:
        return "🟡"
    return "⚪"


def should_notify(score: float, threshold: float = NOTIFICATION_THRESHOLD) -> bool:
    """Return True if the score meets the notification threshold (Section 21)."""
    return score >= threshold
