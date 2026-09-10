"""
Career Tracker — Fresher Classifier

Implements Section 10 of MASTER DEVELOPMENT PROMPT.

Classifies jobs by fresher-eligibility using positive and negative signals.
Returns a classification label rather than a binary yes/no so the pipeline
can handle ambiguous cases intelligently (Section 10: LOWER_PRIORITY).

Positive signals:
  fresher, freshers, graduate, recent graduate, entry level, entry-level,
  0 years, 0–1 years, 0-1 years, trainee, GET, graduate engineer trainee,
  associate, junior, intern, campus, early career

Negative signals (hard rejects):
  5+ years, 6+ years, 7+ years, senior, lead, principal, staff,
  manager, architect

Ambiguous (LOWER_PRIORITY rather than rejection):
  e.g., "Software Engineer — 2 years preferred"
"""

from __future__ import annotations

import re
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class FresherEligibility(str, Enum):
    """Fresher eligibility classification result."""

    ELIGIBLE = "eligible"           # Strong positive fresher signals
    LOWER_PRIORITY = "lower_priority"  # Ambiguous — may be suitable (2 years preferred, etc.)
    INELIGIBLE = "ineligible"       # Clear negative signals (senior, 5+ years, etc.)
    UNKNOWN = "unknown"             # No signals detected


# --- Positive fresher signal patterns (Section 10) ---
POSITIVE_PATTERNS: list[tuple[str, float]] = [
    # Explicit fresher markers
    (r"\bfresher[s]?\b", 1.0),
    (r"\bfresh\s+graduate\b", 1.0),
    (r"\brecent\s+graduate\b", 1.0),
    (r"\bcampus\s+hire\b", 1.0),
    (r"\bcampus\s+recruit(?:ment)?\b", 1.0),
    (r"\boff[- ]?campus\b", 0.9),
    (r"\bpool\s+campus\b", 0.9),
    (r"\bwalk[- ]?in\b", 0.8),
    # Trainee / GET
    (r"\bgraduate\s+engineer\s+trainee\b", 1.0),
    (r"\bmanagement\s+trainee\b", 0.9),
    (r"\b[Gg][Ee][Tt]\b", 0.9),
    (r"\btrainee\b", 0.85),
    # Entry level
    (r"\bentry[- ]level\b", 1.0),
    (r"\bearly[- ]career\b", 1.0),
    (r"\bnew\s+grad\b", 1.0),
    # Experience bands — strong
    (r"\b0\s*[-–]\s*1\s+year[s]?\b", 1.0),
    (r"\b0\s+to\s+1\s+year[s]?\b", 1.0),
    (r"\bno\s+experience\s+required\b", 1.0),
    (r"\b0\s+year[s]?\s+experience\b", 1.0),
    # Experience bands — moderate
    (r"\b0\s*[-–]\s*2\s+year[s]?\b", 0.85),
    (r"\b0\s+to\s+2\s+year[s]?\b", 0.85),
    (r"\bless\s+than\s+1\s+year\b", 0.9),
    # Title-level positive
    (r"\bjunior\b", 0.8),
    (r"\bjr\.?\b", 0.8),
    (r"\bassociate\s+(?:software|developer|engineer)\b", 0.9),
    (r"\bintern(?:ship)?\b", 0.9),
    # Education hints
    (r"\b(?:b\.?e|b\.?tech|mca|bca|m\.?sc)\b", 0.5),
]

# --- Hard negative signal patterns (Section 10) ---
# Format: (regex_pattern, weight, title_only)
# title_only=True: only checked in title (prevents false positives from description context)
NEGATIVE_PATTERNS: list[tuple[str, float, bool]] = [
    (r"\b(?:5|6|7|8|9|10)\+?\s+year[s]?\b", 1.0, False),
    (r"\bminimum\s+(?:5|6|7|8|9|10)\s+year[s]?\b", 1.0, False),
    (r"\bat\s+least\s+(?:5|6|7|8|9|10)\s+year[s]?\b", 1.0, False),
    # 'senior' standalone: title-only to avoid false positives like 'work with senior engineers'
    (r"\bsenior\b", 1.0, True),
    (r"\blead\s+(?:developer|engineer|architect)\b", 1.0, False),
    (r"\btech(?:nical)?\s+lead\b", 1.0, False),
    (r"\bprincipal\s+(?:engineer|architect|developer)\b", 1.0, False),
    (r"\bstaff\s+(?:engineer|developer)\b", 1.0, False),
    (r"\bengineering\s+manager\b", 1.0, False),
    (r"\bmanager\b(?!\s+trainee)", 0.9, True),  # Title-only: 'manager' but not 'management trainee'
    (r"\bdirector\s+of\b", 1.0, False),
    (r"\bhead\s+of\b", 1.0, False),
    (r"\bvp\s+of\b", 1.0, False),
    (r"\bvice\s+president\b", 1.0, False),
    (r"\bchief\s+(?:technology|information|data)\b", 1.0, False),
    (r"\barchitect\b(?!\s+trainee)", 0.9, True),  # Title-only: 'architect' but not 'architect trainee'
]

# --- Ambiguous (lower priority) patterns ---
# These are NOT hard rejects. Candidate can still apply, just lower priority.
AMBIGUOUS_PATTERNS: list[tuple[str, float]] = [
    (r"\b[12]\s*[-–]\s*3\s+year[s]?\b", 0.7),
    (r"\b[12]\s+to\s+3\s+year[s]?\b", 0.7),
    (r"\b[23]\s+year[s]?\s+preferred\b", 0.6),
    (r"\b[12]\s+year[s]?\s+experience\b", 0.7),
    (r"\bsome\s+experience\b", 0.6),
    (r"\bprofessional\s+experience\b", 0.5),
]


def classify_fresher_eligibility(
    text: str,
    *,
    title: Optional[str] = None,
    allow_lower_priority: bool = True,
) -> tuple[FresherEligibility, float, list[str]]:
    """
    Classify whether a job is fresher-eligible based on its text.

    Analyzes title and description for positive/negative/ambiguous signals.
    Title signals are given higher weight.

    Args:
        text: Job description text to analyze.
        title: Job title (gets extra weight if provided).
        allow_lower_priority: If True, ambiguous cases return LOWER_PRIORITY
                              instead of INELIGIBLE.

    Returns:
        Tuple of (FresherEligibility, confidence_score, matched_signals).
    """
    combined = text.lower().strip()
    title_text = (title or "").lower().strip()

    matched_positive: list[str] = []
    matched_negative: list[str] = []
    matched_ambiguous: list[str] = []

    positive_score = 0.0
    negative_score = 0.0

    # Check negative patterns first (hard rejection signals)
    for pattern, weight, title_only in NEGATIVE_PATTERNS:
        # Give negative patterns higher weight in title
        if title_text and re.search(pattern, title_text):
            negative_score += weight * 1.5  # Title is more authoritative
            matched_negative.append(f"[title] {pattern}")
        elif not title_only and re.search(pattern, combined):
            # Only check description for non title_only patterns
            negative_score += weight
            matched_negative.append(pattern)

    # If strong negative signals in title — immediately INELIGIBLE
    if negative_score >= 1.0:
        logger.debug(
            "Job classified INELIGIBLE (negative_score=%.2f): %s",
            negative_score,
            matched_negative[:3],
        )
        return FresherEligibility.INELIGIBLE, min(negative_score / 2.0, 1.0), matched_negative

    # Check positive patterns
    for pattern, weight in POSITIVE_PATTERNS:
        if title_text and re.search(pattern, title_text):
            positive_score += weight * 1.3  # Title is more authoritative
            matched_positive.append(f"[title] {pattern}")
        elif re.search(pattern, combined):
            positive_score += weight
            matched_positive.append(pattern)

    # Strong positive signals → ELIGIBLE
    if positive_score >= 0.8:
        confidence = min(positive_score / 2.0, 1.0)
        logger.debug(
            "Job classified ELIGIBLE (positive_score=%.2f)", positive_score
        )
        return FresherEligibility.ELIGIBLE, confidence, matched_positive

    # Check ambiguous patterns
    if allow_lower_priority:
        for pattern, weight in AMBIGUOUS_PATTERNS:
            if re.search(pattern, combined):
                matched_ambiguous.append(pattern)

        if matched_ambiguous:
            logger.debug(
                "Job classified LOWER_PRIORITY (ambiguous): %s",
                matched_ambiguous[:3],
            )
            return FresherEligibility.LOWER_PRIORITY, 0.5, matched_ambiguous

    # Mild positive signals → ELIGIBLE with lower confidence
    if positive_score > 0:
        confidence = min(positive_score / 2.0, 0.7)
        return FresherEligibility.ELIGIBLE, confidence, matched_positive

    return FresherEligibility.UNKNOWN, 0.0, []


def is_hard_reject(title: str) -> bool:
    """
    Quick deterministic check if a title is a hard rejection (Section 9).

    Used before any AI analysis to cheaply filter obviously wrong-level jobs.
    All patterns are applied to the title — the function is title-only by design.
    """
    title_lower = title.lower().strip()
    for pattern, _weight, _title_only in NEGATIVE_PATTERNS:
        if re.search(pattern, title_lower):
            return True
    return False
