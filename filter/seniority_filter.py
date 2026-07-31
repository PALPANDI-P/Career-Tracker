"""
Career Tracker — Seniority Filter

Regex-based filter that matches job titles against configurable
seniority level patterns. Purely deterministic — no LLM needed.

This runs BEFORE matching to eliminate obviously wrong-level jobs
(e.g., filtering out "VP of Engineering" when targeting junior roles).

Also includes India-specific fresher/training keyword detection
for the Indian IT job market.
"""

from __future__ import annotations

import logging
import re

from schema.job import Job, JobCategory, SeniorityLevel

logger = logging.getLogger(__name__)

# ─── Seniority Pattern Definitions ──────────────────
# Each seniority level maps to a list of regex patterns
# that match common title variations.

SENIORITY_PATTERNS: dict[SeniorityLevel, list[str]] = {
    SeniorityLevel.INTERN: [
        r"\bintern\b",
        r"\binternship\b",
        r"\bco-?op\b",
        r"\btrainee\b",
        r"\btraining\b",
    ],
    SeniorityLevel.ENTRY: [
        r"\bentry[- ]?level\b",
        r"\bnew\s+grad\b",
        r"\bjunior\b",
        r"\bassociate\b(?!.*director)",
        r"\b[Ii]\b(?=\s|$)",  # "Engineer I"
        r"\bfresher\b",
        r"\bfreshers\b",
        r"\bfresh\s+graduate\b",
        r"\bcampus\s+hire\b",
        r"\bgraduate\s+engineer\s+trainee\b",
        r"\b[Gg][Ee][Tt]\b",  # Graduate Engineer Trainee
    ],
    SeniorityLevel.JUNIOR: [
        r"\bjunior\b",
        r"\bjr\.?\b",
        r"\bentry\b",
        r"\bassociate\b(?!.*director)",
    ],
    SeniorityLevel.MID: [
        r"\bmid[- ]?level\b",
        r"\b[Ii]{2}\b",  # "Engineer II"
        r"\b[Ii]{3}\b",  # "Engineer III"
    ],
    SeniorityLevel.SENIOR: [
        r"\bsenior\b",
        r"\bsr\.?\b",
        r"\b[Ii]{3,4}\b",  # "Engineer III" / "IV"
    ],
    SeniorityLevel.STAFF: [
        r"\bstaff\b",
        r"\bprincipal\b",
    ],
    SeniorityLevel.PRINCIPAL: [
        r"\bprincipal\b",
        r"\bdistinguished\b",
        r"\bfellow\b",
    ],
    SeniorityLevel.LEAD: [
        r"\blead\b",
        r"\btech\s+lead\b",
        r"\bteam\s+lead\b",
    ],
    SeniorityLevel.MANAGER: [
        r"\bmanager\b",
        r"\bengineering\s+manager\b",
        r"\bem\b",
    ],
    SeniorityLevel.DIRECTOR: [
        r"\bdirector\b",
        r"\bhead\s+of\b",
    ],
    SeniorityLevel.VP: [
        r"\bvp\b",
        r"\bvice\s+president\b",
    ],
    SeniorityLevel.EXECUTIVE: [
        r"\bcto\b",
        r"\bceo\b",
        r"\bchief\b",
        r"\bc-suite\b",
        r"\bexecutive\b",
    ],
}


# ─── India-Specific Fresher/Training Keywords ──────────
# Patterns specific to the Indian IT job market for detecting
# fresher-eligible, training, and campus recruitment roles.

FRESHER_KEYWORDS: list[str] = [
    r"\bfresher\b",
    r"\bfreshers\b",
    r"\bfresh\s+graduate\b",
    r"\bcampus\s+hire\b",
    r"\bcampus\s+recruitment\b",
    r"\boff[- ]?campus\b",
    r"\bpool\s+campus\b",
    r"\bwalk[- ]?in\b",
    r"\btrainee\b",
    r"\btraining\b",
    r"\bgraduate\s+engineer\s+trainee\b",
    r"\bmanagement\s+trainee\b",
    r"\b[Gg][Ee][Tt]\b",
    r"\bentry\s+level\b",
    r"\b0[- ]?1\s+year\b",
    r"\b0\s+to\s+1\s+year\b",
    r"\bno\s+experience\b",
    r"\b0[- ]?2\s+years?\b",
    r"\b0\s+to\s+2\s+years?\b",
    r"\bmca\b",
    r"\bbca\b",
    r"\bb\.?tech\b",
    r"\bb\.?e\b",
    r"\bm\.?sc\b",
]


# Map fresher keywords to job categories
FRESHER_CATEGORY_MAP: dict[str, JobCategory] = {
    r"\bfresher\b": JobCategory.FRESHER,
    r"\bfreshers\b": JobCategory.FRESHER,
    r"\bfresh\s+graduate\b": JobCategory.FRESHER,
    r"\bcampus\s+hire\b": JobCategory.CAMPUS,
    r"\bcampus\s+recruitment\b": JobCategory.CAMPUS,
    r"\boff[- ]?campus\b": JobCategory.CAMPUS,
    r"\bpool\s+campus\b": JobCategory.CAMPUS,
    r"\bwalk[- ]?in\b": JobCategory.WALK_IN,
    r"\btrainee\b": JobCategory.TRAINING,
    r"\btraining\b": JobCategory.TRAINING,
    r"\bgraduate\s+engineer\s+trainee\b": JobCategory.TRAINING,
    r"\bmanagement\s+trainee\b": JobCategory.TRAINING,
    r"\b[Gg][Ee][Tt]\b": JobCategory.TRAINING,
    r"\bintern\b": JobCategory.INTERNSHIP,
    r"\binternship\b": JobCategory.INTERNSHIP,
}


def detect_seniority(title: str) -> SeniorityLevel:
    """
    Detect the seniority level from a job title using regex patterns.

    Checks patterns from most specific (executive) to least specific.
    Returns SeniorityLevel.UNKNOWN if no pattern matches.
    """
    title_lower = title.lower().strip()

    # Check in order from most senior to least, so more specific patterns
    # take priority (e.g., "VP" before "Manager")
    check_order = [
        SeniorityLevel.EXECUTIVE,
        SeniorityLevel.VP,
        SeniorityLevel.DIRECTOR,
        SeniorityLevel.PRINCIPAL,
        SeniorityLevel.STAFF,
        SeniorityLevel.LEAD,
        SeniorityLevel.MANAGER,
        SeniorityLevel.SENIOR,
        SeniorityLevel.MID,
        SeniorityLevel.JUNIOR,
        SeniorityLevel.ENTRY,
        SeniorityLevel.INTERN,
    ]

    for level in check_order:
        patterns = SENIORITY_PATTERNS.get(level, [])
        for pattern in patterns:
            if re.search(pattern, title_lower):
                return level

    return SeniorityLevel.UNKNOWN


def detect_fresher_category(text: str) -> tuple[bool, JobCategory]:
    """
    Detect if a job title or description indicates a fresher/training role.

    Checks against India-specific fresher keywords and returns
    both a boolean (is fresher eligible) and the specific category.

    Args:
        text: Job title or description text to analyze

    Returns:
        Tuple of (is_fresher_eligible, job_category)
    """
    text_lower = text.lower().strip()

    for pattern, category in FRESHER_CATEGORY_MAP.items():
        if re.search(pattern, text_lower):
            return True, category

    # Also check the general fresher keywords list
    for pattern in FRESHER_KEYWORDS:
        if re.search(pattern, text_lower):
            return True, JobCategory.FRESHER

    return False, JobCategory.UNKNOWN


def detect_job_category(job: Job) -> tuple[bool, JobCategory]:
    """
    Combined detection: checks both title and description for fresher eligibility.

    Args:
        job: Job object to analyze

    Returns:
        Tuple of (is_fresher_eligible, job_category)
    """
    # Check title first (higher priority)
    is_fresher, category = detect_fresher_category(job.title)
    if is_fresher:
        return True, category

    # Check description if title didn't match
    if job.description:
        # Only check first 500 chars of description to avoid false positives
        desc_snippet = job.description[:500]
        is_fresher, category = detect_fresher_category(desc_snippet)
        if is_fresher:
            return True, category

    return False, JobCategory.UNKNOWN


def filter_by_seniority(
    jobs: list[Job],
    target_levels: list[str],
    include_unknown: bool = True,
) -> list[Job]:
    """
    Filter jobs to only those matching the target seniority levels.

    Args:
        jobs: List of Job objects to filter
        target_levels: List of seniority level strings (e.g., ["entry", "junior", "mid"])
        include_unknown: Whether to include jobs where seniority can't be determined

    Returns:
        Filtered list of Job objects
    """
    if not target_levels:
        return jobs

    # Normalize target levels to SeniorityLevel enum values
    target_set: set[SeniorityLevel] = set()
    for level_str in target_levels:
        try:
            target_set.add(SeniorityLevel(level_str.lower()))
        except ValueError:
            logger.warning("Unknown seniority level: %s", level_str)

    if include_unknown:
        target_set.add(SeniorityLevel.UNKNOWN)

    filtered: list[Job] = []

    for job in jobs:
        # Detect seniority from title if not already set
        detected = detect_seniority(job.title)

        if detected in target_set:
            filtered.append(job)
        else:
            logger.debug(
                "Filtered out: '%s' (detected: %s, targets: %s)",
                job.title,
                detected.value,
                [t.value for t in target_set],
            )

    logger.info(
        "Seniority filter: %d/%d jobs match target levels %s",
        len(filtered),
        len(jobs),
        [t.value for t in target_set if t != SeniorityLevel.UNKNOWN],
    )

    return filtered

