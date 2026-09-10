"""
Career Tracker — Role Taxonomy

Implements Section 12 of MASTER DEVELOPMENT PROMPT.

Maps job titles into taxonomy categories without relying solely on exact keywords.
Uses pattern matching with a predefined role taxonomy tree.

Taxonomy:
  Software Development
    ├── Python
    ├── Backend
    ├── Full Stack
    ├── Java
    └── General Software

  AI / ML
    ├── Machine Learning
    ├── NLP
    ├── Generative AI
    ├── Computer Vision
    └── AI Engineering

  Data
    ├── Data Analyst
    ├── Junior Data Scientist
    └── ML/Data Engineering

  Testing
    ├── QA
    ├── Test Engineer
    └── Automation Testing
"""

from __future__ import annotations

import re
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class TaxonomyCategory(str, Enum):
    """Top-level taxonomy categories."""

    SOFTWARE_DEVELOPMENT = "software_development"
    AI_ML = "ai_ml"
    DATA = "data"
    TESTING = "testing"
    DEVOPS = "devops"
    UNKNOWN = "unknown"


class TaxonomySubcategory(str, Enum):
    """Fine-grained subcategories within each top-level taxonomy."""

    # Software Development
    PYTHON = "python"
    BACKEND = "backend"
    FULL_STACK = "full_stack"
    JAVA = "java"
    GENERAL_SOFTWARE = "general_software"
    FRONTEND = "frontend"
    MOBILE = "mobile"

    # AI / ML
    MACHINE_LEARNING = "machine_learning"
    NLP = "nlp"
    GENERATIVE_AI = "generative_ai"
    COMPUTER_VISION = "computer_vision"
    AI_ENGINEERING = "ai_engineering"

    # Data
    DATA_ANALYST = "data_analyst"
    DATA_SCIENTIST = "data_scientist"
    DATA_ENGINEERING = "data_engineering"

    # Testing
    QA = "qa"
    TEST_ENGINEER = "test_engineer"
    AUTOMATION_TESTING = "automation_testing"

    # DevOps
    DEVOPS = "devops"
    CLOUD = "cloud"
    SRE = "sre"

    UNKNOWN = "unknown"


# ─── Role Pattern Definitions ─────────────────────────────────────────────
# Format: (regex_pattern, category, subcategory, priority)
# Higher priority = matched first when multiple patterns match

ROLE_PATTERNS: list[tuple[str, TaxonomyCategory, TaxonomySubcategory, int]] = [
    # --- AI / ML (high priority, checked first) ---
    (r"\bgenerative\s*ai\b", TaxonomyCategory.AI_ML, TaxonomySubcategory.GENERATIVE_AI, 100),
    (r"\bgen\s*ai\b", TaxonomyCategory.AI_ML, TaxonomySubcategory.GENERATIVE_AI, 100),
    (r"\bllm\b", TaxonomyCategory.AI_ML, TaxonomySubcategory.GENERATIVE_AI, 95),
    (r"\blarge\s+language\s+model", TaxonomyCategory.AI_ML, TaxonomySubcategory.GENERATIVE_AI, 95),
    (r"\bnlp\b", TaxonomyCategory.AI_ML, TaxonomySubcategory.NLP, 95),
    (r"\bnatural\s+language\s+process", TaxonomyCategory.AI_ML, TaxonomySubcategory.NLP, 95),
    (r"\bcomputer\s+vision\b", TaxonomyCategory.AI_ML, TaxonomySubcategory.COMPUTER_VISION, 95),
    (r"\bocr\b", TaxonomyCategory.AI_ML, TaxonomySubcategory.COMPUTER_VISION, 90),
    (r"\bmachine\s+learning\b", TaxonomyCategory.AI_ML, TaxonomySubcategory.MACHINE_LEARNING, 90),
    (r"\bml\s+engineer", TaxonomyCategory.AI_ML, TaxonomySubcategory.MACHINE_LEARNING, 90),
    (r"\bai\s*(?:/|and)?\s*ml\b", TaxonomyCategory.AI_ML, TaxonomySubcategory.AI_ENGINEERING, 90),
    (r"\bai\s+engineer\b", TaxonomyCategory.AI_ML, TaxonomySubcategory.AI_ENGINEERING, 90),
    (r"\bdata\s+scientist\b", TaxonomyCategory.DATA, TaxonomySubcategory.DATA_SCIENTIST, 90),

    # --- Data ---
    (r"\bdata\s+engineer\b", TaxonomyCategory.DATA, TaxonomySubcategory.DATA_ENGINEERING, 85),
    (r"\bdata\s+analyst\b", TaxonomyCategory.DATA, TaxonomySubcategory.DATA_ANALYST, 85),
    (r"\betl\b", TaxonomyCategory.DATA, TaxonomySubcategory.DATA_ENGINEERING, 80),
    (r"\bdata\s+pipeline", TaxonomyCategory.DATA, TaxonomySubcategory.DATA_ENGINEERING, 80),

    # --- Testing ---
    (r"\bautomation\s+test", TaxonomyCategory.TESTING, TaxonomySubcategory.AUTOMATION_TESTING, 85),
    (r"\bselenium\b", TaxonomyCategory.TESTING, TaxonomySubcategory.AUTOMATION_TESTING, 80),
    (r"\bqa\s+engineer\b", TaxonomyCategory.TESTING, TaxonomySubcategory.QA, 85),
    (r"\bquality\s+assurance\b", TaxonomyCategory.TESTING, TaxonomySubcategory.QA, 85),
    (r"\btest\s+engineer\b", TaxonomyCategory.TESTING, TaxonomySubcategory.TEST_ENGINEER, 85),
    (r"\bsdet\b", TaxonomyCategory.TESTING, TaxonomySubcategory.AUTOMATION_TESTING, 85),

    # --- DevOps ---
    (r"\bdevops\b", TaxonomyCategory.DEVOPS, TaxonomySubcategory.DEVOPS, 85),
    (r"\bsite\s+reliability\b", TaxonomyCategory.DEVOPS, TaxonomySubcategory.SRE, 85),
    (r"\bsre\b", TaxonomyCategory.DEVOPS, TaxonomySubcategory.SRE, 85),
    (r"\bcloud\s+engineer\b", TaxonomyCategory.DEVOPS, TaxonomySubcategory.CLOUD, 80),

    # --- Software: Python ---
    (r"\bpython\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.PYTHON, 80),
    (r"\bflask\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.PYTHON, 75),
    (r"\bfastapi\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.PYTHON, 75),
    (r"\bdjango\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.PYTHON, 75),

    # --- Software: Backend ---
    (r"\bbackend\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.BACKEND, 75),
    (r"\bback\s*end\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.BACKEND, 75),
    (r"\brest\s*(?:ful)?\s*api\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.BACKEND, 70),
    (r"\bmicroservice[s]?\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.BACKEND, 70),
    (r"\bserver[- ]side\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.BACKEND, 70),

    # --- Software: Full Stack ---
    (r"\bfull\s*[- ]?stack\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.FULL_STACK, 75),

    # --- Software: Java ---
    (r"\bjava\s+developer\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.JAVA, 75),
    (r"\bspring\s+boot\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.JAVA, 70),

    # --- Software: General ---
    (r"\bsoftware\s+engineer\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.GENERAL_SOFTWARE, 60),
    (r"\bsoftware\s+developer\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.GENERAL_SOFTWARE, 60),
    (r"\bapplication\s+developer\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.GENERAL_SOFTWARE, 60),
    (r"\bgraduate\s+engineer\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.GENERAL_SOFTWARE, 60),
    (r"\bget\b", TaxonomyCategory.SOFTWARE_DEVELOPMENT, TaxonomySubcategory.GENERAL_SOFTWARE, 55),
]


def classify_role(title: str, description: str = "") -> tuple[TaxonomyCategory, TaxonomySubcategory, float]:
    """
    Classify a job title into a taxonomy category and subcategory.

    Patterns are checked in priority order. Title matches are weighted higher
    than description matches.

    Args:
        title: Job title string.
        description: Job description (optional, used for additional context).

    Returns:
        Tuple of (TaxonomyCategory, TaxonomySubcategory, confidence_score)
    """
    title_lower = title.lower().strip()
    desc_lower = description.lower()[:500] if description else ""

    best_match: Optional[tuple[TaxonomyCategory, TaxonomySubcategory, int, bool]] = None
    # (category, subcategory, priority, is_title_match)

    for pattern, category, subcategory, priority in ROLE_PATTERNS:
        # Title match — extra weight
        if re.search(pattern, title_lower):
            effective_priority = priority + 20  # Title boost
            if best_match is None or effective_priority > best_match[2]:
                best_match = (category, subcategory, effective_priority, True)

        # Description match
        elif desc_lower and re.search(pattern, desc_lower):
            if best_match is None or priority > best_match[2]:
                best_match = (category, subcategory, priority, False)

    if best_match is None:
        return TaxonomyCategory.UNKNOWN, TaxonomySubcategory.UNKNOWN, 0.0

    category, subcategory, priority, is_title = best_match
    # Confidence: normalized 0-1 from priority (max=120)
    confidence = min(priority / 120.0, 1.0)

    logger.debug(
        "Role '%s' classified as %s/%s (confidence=%.2f, title=%s)",
        title,
        category.value,
        subcategory.value,
        confidence,
        is_title,
    )
    return category, subcategory, confidence


def is_candidate_relevant_role(
    title: str,
    description: str = "",
    candidate_taxonomy: Optional[list[str]] = None,
) -> bool:
    """
    Check if a job role falls within the candidate's target taxonomy.

    Default candidate taxonomy covers Python, Backend, AI/ML, Data, Testing.

    Args:
        title: Job title.
        description: Job description.
        candidate_taxonomy: List of TaxonomyCategory value strings the
                            candidate is targeting.

    Returns:
        True if the role is within the candidate's taxonomy.
    """
    if candidate_taxonomy is None:
        # Default: Palpandi P's target taxonomy
        candidate_taxonomy = [
            TaxonomyCategory.SOFTWARE_DEVELOPMENT.value,
            TaxonomyCategory.AI_ML.value,
            TaxonomyCategory.DATA.value,
            TaxonomyCategory.TESTING.value,
        ]

    category, _, confidence = classify_role(title, description)
    return category.value in candidate_taxonomy
