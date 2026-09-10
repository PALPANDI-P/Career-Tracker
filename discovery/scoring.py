"""
Career Tracker — Company Scoring & Priority Engine

Calculates company-level hiring activity and candidate relevance scores:
1. Hiring Activity Score (0-100):
   - Number of open roles
   - Recent job postings (freshness)
   - Engineering role ratio
   - Fresher/trainee presence

2. Candidate Relevance Score (0-100):
   - Python, AI/ML, backend, NLP, data roles
   - Entry-level / graduate eligibility

3. Overall Company Score (0-100):
   - Hiring Activity       (25%)
   - Candidate Relevance   (25%)
   - Fresher Opportunity   (15%)
   - Role Availability     (15%)
   - Company Type Fit      (10%)
   - Location Fit          (10%)

4. Monitor Priority Tiers:
   - P0: Highly relevant + actively hiring (30m refresh)
   - P1: Relevant + active (60m refresh)
   - P2: Moderate relevance (2-4h refresh)
   - P3: Low activity / low relevance (daily refresh)

5. Dynamic Feedback Loop:
   - Adjusts company priority upwards when relevant matches are found
   - Decreases priority gracefully if postings are consistently irrelevant
"""

from __future__ import annotations

import logging
from typing import Sequence

from schema.company_schema import CompanyPriority

logger = logging.getLogger(__name__)

TARGET_KEYWORDS = [
    "python", "flask", "fastapi", "django", "ai", "machine learning", "ml",
    "nlp", "backend", "software engineer", "developer", "trainee", "fresher",
    "graduate engineer", "data engineer", "data analyst"
]

PREFERRED_CITIES = [
    "chennai", "coimbatore", "madurai", "trichy", "bangalore", "bengaluru",
    "mysore", "hyderabad", "pune", "kochi", "trivandrum", "remote", "india"
]


def calculate_hiring_activity_score(
    open_roles: int,
    recent_roles_count: int = 0,
    engineering_ratio: float = 0.5,
    fresher_role_count: int = 0,
) -> float:
    """Calculate company hiring activity score from 0.0 to 100.0."""
    score = 0.0

    # Role count contribution (up to 40 pts)
    if open_roles > 0:
        score += min(open_roles * 4.0, 40.0)

    # Recent new roles (up to 25 pts)
    if recent_roles_count > 0:
        score += min(recent_roles_count * 5.0, 25.0)

    # Engineering focus ratio (up to 20 pts)
    score += engineering_ratio * 20.0

    # Fresher role presence (up to 15 pts)
    if fresher_role_count > 0:
        score += min(fresher_role_count * 5.0, 15.0)

    return round(min(score, 100.0), 2)


def calculate_candidate_relevance_score(
    job_titles: Sequence[str],
    fresher_role_count: int = 0,
    locations: Sequence[str] | None = None,
) -> float:
    """Calculate how relevant a company's hiring is to the MCA candidate profile."""
    if not job_titles:
        return 20.0

    relevant_count = 0
    python_ai_count = 0

    for title in job_titles:
        t = title.lower()
        if any(k in t for k in TARGET_KEYWORDS):
            relevant_count += 1
        if "python" in t or "ai" in t or "ml" in t or "nlp" in t or "backend" in t:
            python_ai_count += 1

    total = len(job_titles)
    rel_ratio = relevant_count / total if total else 0
    py_ratio = python_ai_count / total if total else 0

    score = (rel_ratio * 40.0) + (py_ratio * 35.0)

    if fresher_role_count > 0:
        score += 15.0

    # Location fit (up to 10 pts)
    loc_str = " ".join(locations or []).lower()
    if any(city in loc_str for city in PREFERRED_CITIES):
        score += 10.0

    return round(min(score, 100.0), 2)


def calculate_company_score(
    hiring_activity: float,
    candidate_relevance: float,
    fresher_opportunity_score: float = 50.0,
    role_availability_score: float = 50.0,
    company_type_fit: float = 70.0,
    location_fit: float = 80.0,
) -> tuple[float, CompanyPriority]:
    """
    Weighted calculation of overall company priority score (0-100).
    """
    overall = (
        (hiring_activity * 0.25)
        + (candidate_relevance * 0.25)
        + (fresher_opportunity_score * 0.15)
        + (role_availability_score * 0.15)
        + (company_type_fit * 0.10)
        + (location_fit * 0.10)
    )
    overall = round(min(max(overall, 0.0), 100.0), 2)

    # Determine priority tier
    if overall >= 75.0 or (candidate_relevance >= 80.0 and hiring_activity >= 50.0):
        priority = CompanyPriority.P0
    elif overall >= 60.0 or candidate_relevance >= 65.0:
        priority = CompanyPriority.P1
    elif overall >= 40.0:
        priority = CompanyPriority.P2
    else:
        priority = CompanyPriority.P3

    return overall, priority


def apply_feedback_adjustment(
    current_priority: CompanyPriority,
    total_jobs_seen: int,
    relevant_matches: int,
    high_score_matches: int,
) -> CompanyPriority:
    """
    Dynamic feedback loop:
    Promotes company priority when high-match jobs are found;
    demotes priority gracefully when jobs are consistently irrelevant.
    """
    if total_jobs_seen == 0:
        return current_priority

    match_ratio = relevant_matches / total_jobs_seen

    # Upgrade priority if producing high-quality matches
    if high_score_matches >= 3 or (total_jobs_seen >= 5 and match_ratio >= 0.5):
        if current_priority == CompanyPriority.P1:
            return CompanyPriority.P0
        elif current_priority == CompanyPriority.P2:
            return CompanyPriority.P1
        elif current_priority == CompanyPriority.P3:
            return CompanyPriority.P2

    # Downgrade priority if many jobs seen but 0 relevant matches
    if total_jobs_seen >= 20 and relevant_matches == 0:
        if current_priority == CompanyPriority.P0:
            return CompanyPriority.P1
        elif current_priority == CompanyPriority.P1:
            return CompanyPriority.P2
        elif current_priority == CompanyPriority.P2:
            return CompanyPriority.P3

    return current_priority
