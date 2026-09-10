"""
Career Tracker — Resume Selector

Implements Section 18 of MASTER DEVELOPMENT PROMPT.

Automatically selects the most appropriate resume variant for a given job
based on role taxonomy, skill overlap, and job description analysis.

Resume variants:
  - resume_python_backend.pdf     → Python Backend / API / Flask / FastAPI roles
  - resume_ai_ml.pdf              → AI Engineer / ML Engineer / NLP / GenAI roles
  - resume_software_developer.pdf → General Software Engineer / Full Stack roles
  - resume_general_fresher.pdf    → Trainee / GET / Intern / Campus roles
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── Resume Variant Definitions ─────────────────────────────────────────
# Each variant has a list of (keyword_pattern, score_boost) tuples
# Scoring is additive — the variant with the highest total score wins.

RESUME_VARIANTS: list[dict[str, Any]] = [
    {
        "id": "python_backend",
        "name": "Python Backend Resume",
        "file": "PALPANDI_P_Resume_Python_Developer .pdf",
        "target_roles": [
            "Python Developer",
            "Backend Developer",
            "Python Backend Developer",
            "Flask Developer",
            "FastAPI Developer",
            "API Developer",
            "Junior Python Developer",
        ],
        "trigger_keywords": [
            "python", "flask", "fastapi", "django", "backend",
            "rest api", "restful", "sqlalchemy", "postgresql",
            "microservices", "server-side", "api development",
        ],
        "trigger_titles": [
            "python", "backend", "flask", "fastapi", "django", "api developer",
        ],
        "weight": 1.0,
    },
    {
        "id": "ai_ml",
        "name": "AI/ML Resume",
        "file": "PALPANDI_P_Resume_AI_ML_Developer .pdf",
        "target_roles": [
            "AI Engineer",
            "AI/ML Engineer",
            "Machine Learning Engineer",
            "NLP Engineer",
            "Generative AI Engineer",
            "Data Scientist",
            "Junior Data/AI Engineer",
        ],
        "trigger_keywords": [
            "machine learning", "ml", "nlp", "ai", "deep learning",
            "scikit-learn", "sklearn", "tensorflow", "pytorch", "bert",
            "transformers", "generative ai", "llm", "ocr", "computer vision",
            "openCV", "whisper", "hugging face", "natural language",
            "google gemini", "gemini ai",
        ],
        "trigger_titles": [
            "ai", "ml", "machine learning", "nlp", "generative ai",
            "data scientist", "computer vision",
        ],
        "weight": 1.0,
    },
    {
        "id": "software_developer",
        "name": "Software Developer Resume",
        "file": "PALPANDI_P_Resume_Backend_Developer.pdf",
        "target_roles": [
            "Software Developer",
            "Software Engineer",
            "Full Stack Developer",
            "Application Developer",
            "Junior Software Engineer",
            "Associate Software Engineer",
        ],
        "trigger_keywords": [
            "software engineer", "software developer", "full stack",
            "react", "javascript", "java", "spring boot", "web development",
            "application development", "oops", "object oriented",
        ],
        "trigger_titles": [
            "software engineer", "software developer", "full stack",
            "application developer", "systems engineer",
        ],
        "weight": 0.9,
    },
    {
        "id": "general_fresher",
        "name": "General Fresher Resume",
        "file": "resume_general_fresher.pdf",
        "target_roles": [
            "Graduate Engineer Trainee",
            "GET",
            "Software Engineer Trainee",
            "QA/Test Engineer Trainee",
            "Intern",
        ],
        "trigger_keywords": [
            "fresher", "trainee", "get", "graduate engineer",
            "campus", "entry level", "intern", "0-1 years", "associate",
        ],
        "trigger_titles": [
            "trainee", "get", "intern", "fresher", "graduate engineer",
        ],
        "weight": 0.85,
    },
]


def select_resume(
    job_title: str,
    job_description: str,
    resume_variants: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Select the best resume variant for a given job.

    Scoring approach:
      - Title keyword match: +3.0 per match
      - Description keyword match: +1.0 per match
      - Variant weight multiplier applied to total

    Args:
        job_title: Job title string.
        job_description: Full or partial job description text.
        resume_variants: Override the default variants (for testing/custom profiles).

    Returns:
        Dict with: id, name, file, score, reason
    """
    variants = resume_variants or RESUME_VARIANTS
    title_lower = job_title.lower().strip()
    desc_lower = job_description.lower()[:1000] if job_description else ""

    best_variant = None
    best_score = -1.0
    best_reason = ""

    for variant in variants:
        score = 0.0
        matched_title_kws: list[str] = []
        matched_desc_kws: list[str] = []

        # Title keyword matches (high weight)
        for kw in variant.get("trigger_titles", []):
            if kw.lower() in title_lower:
                score += 3.0
                matched_title_kws.append(kw)

        # Description keyword matches
        for kw in variant.get("trigger_keywords", []):
            if kw.lower() in desc_lower:
                score += 1.0
                matched_desc_kws.append(kw)

        # Apply variant weight
        score *= variant.get("weight", 1.0)

        logger.debug(
            "Resume variant '%s': score=%.1f (title_kws=%s, desc_kws=%s)",
            variant["id"],
            score,
            matched_title_kws[:3],
            matched_desc_kws[:5],
        )

        if score > best_score:
            best_score = score
            best_variant = variant

            # Build reason string
            if matched_title_kws:
                best_reason = f"Title matched: {', '.join(matched_title_kws[:3])}"
            elif matched_desc_kws:
                best_reason = f"Description matched: {', '.join(matched_desc_kws[:3])}"
            else:
                best_reason = "Default selection"

    if best_variant is None:
        # Fallback to general fresher if nothing matches
        best_variant = RESUME_VARIANTS[-1]
        best_reason = "Fallback: no specific role signals detected"

    result = {
        **best_variant,
        "score": round(best_score, 2),
        "reason": best_reason,
    }

    logger.info(
        "Selected resume '%s' for job '%s' (score=%.1f)",
        result["name"],
        job_title,
        best_score,
    )
    return result


def get_resume_metadata(
    resume_variants: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Return metadata for all available resume variants."""
    return resume_variants or RESUME_VARIANTS
