"""
Career Tracker — Company Classification & Evidence Engine

Classifies discovered companies into structural stages:
- STARTUP_EARLY (< 50 employees, Seed / Early stage)
- STARTUP_GROWTH (50-200 employees, Series A/B/C)
- SCALEUP (200-500 employees, late stage)
- MID_SIZE (100-1000 employees, product/SaaS)
- LARGE (> 1000 employees)
- ENTERPRISE (Big Tech / MNC)
- UNKNOWN (Insufficient evidence)

Stores structured evidence strings and confidence ratings.
Rule: Never invent company size or stage. Return UNKNOWN when evidence is lacking.
"""

from __future__ import annotations

import re
import logging
from typing import Any

from schema.company_schema import (
    CompanyClassification,
    CompanyIntelligence,
    CompanyType,
)

logger = logging.getLogger(__name__)


KEYWORDS_AI_ML = [
    "ai", "artificial intelligence", "machine learning", "deep learning", "nlp",
    "llm", "generative ai", "computer vision", "neural network", "data science"
]
KEYWORDS_SAAS = [
    "saas", "software as a service", "b2b saas", "cloud platform", "subscription software"
]
KEYWORDS_FINTECH = [
    "fintech", "payments", "banking", "lending", "wealthtech", "neobank", "crypto"
]
KEYWORDS_DEV_TOOLS = [
    "developer tools", "devtools", "api", "infrastructure", "observability", "devops"
]
KEYWORDS_CYBERSECURITY = [
    "cybersecurity", "security", "threat intelligence", "identity", "zero trust"
]
KEYWORDS_HEALTH = [
    "healthtech", "healthcare", "biotech", "telemedicine", "medtech"
]
KEYWORDS_EDTECH = [
    "edtech", "e-learning", "online education", "upskilling"
]


def classify_company(
    company_name: str,
    raw_snippet: str | None = None,
    job_titles: list[str] | None = None,
    tags: list[str] | None = None,
    employee_count_estimate: int | None = None,
    funding_stage: str | None = None,
) -> CompanyIntelligence:
    """
    Classify a company based on explicit signals and build a structured intelligence profile.
    """
    evidence: list[str] = []
    confidence_signals = 0.0

    text_corpus = f"{company_name} {raw_snippet or ''} {' '.join(job_titles or [])} {' '.join(tags or [])}".lower()

    # 1. Determine Company Type
    company_type = CompanyType.PRODUCT
    if any(k in text_corpus for k in KEYWORDS_AI_ML):
        company_type = CompanyType.AI_ML
        evidence.append("Keywords indicate AI/ML focus")
        confidence_signals += 0.2
    elif any(k in text_corpus for k in KEYWORDS_SAAS):
        company_type = CompanyType.SAAS
        evidence.append("SaaS / Cloud software platform signals detected")
        confidence_signals += 0.2
    elif any(k in text_corpus for k in KEYWORDS_FINTECH):
        company_type = CompanyType.FINTECH
        evidence.append("Fintech / Financial technology focus detected")
        confidence_signals += 0.2
    elif any(k in text_corpus for k in KEYWORDS_DEV_TOOLS):
        company_type = CompanyType.DEV_TOOLS
        evidence.append("Developer tools / API infrastructure focus detected")
        confidence_signals += 0.2
    elif any(k in text_corpus for k in KEYWORDS_CYBERSECURITY):
        company_type = CompanyType.CYBERSECURITY
        evidence.append("Cybersecurity domain detected")
        confidence_signals += 0.2

    # 2. Determine Classification Stage
    classification = CompanyClassification.UNKNOWN
    stage_str = (funding_stage or "").upper()

    if employee_count_estimate and employee_count_estimate > 0:
        if employee_count_estimate < 50:
            classification = CompanyClassification.STARTUP_EARLY
            evidence.append(f"Estimated team size under 50 ({employee_count_estimate} employees)")
            confidence_signals += 0.3
        elif employee_count_estimate <= 200:
            classification = CompanyClassification.STARTUP_GROWTH
            evidence.append(f"Growth startup size ({employee_count_estimate} employees)")
            confidence_signals += 0.3
        elif employee_count_estimate <= 500:
            classification = CompanyClassification.SCALEUP
            evidence.append(f"Scale-up team size ({employee_count_estimate} employees)")
            confidence_signals += 0.3
        elif employee_count_estimate <= 1000:
            classification = CompanyClassification.MID_SIZE
            evidence.append(f"Mid-size product company ({employee_count_estimate} employees)")
            confidence_signals += 0.3
        else:
            classification = CompanyClassification.LARGE
            evidence.append(f"Large company size ({employee_count_estimate} employees)")
            confidence_signals += 0.3
    elif "SEED" in stage_str or "SERIES A" in stage_str or "SERIES_A" in stage_str:
        classification = CompanyClassification.STARTUP_EARLY
        evidence.append(f"Funding stage signal: {stage_str}")
        confidence_signals += 0.3
    elif "SERIES B" in stage_str or "SERIES C" in stage_str:
        classification = CompanyClassification.STARTUP_GROWTH
        evidence.append(f"Growth funding signal: {stage_str}")
        confidence_signals += 0.3
    elif "startup" in text_corpus or "backed" in text_corpus or "venture" in text_corpus:
        classification = CompanyClassification.STARTUP_GROWTH
        evidence.append("General venture-backed startup signals in company description")
        confidence_signals += 0.25
    elif "mid-size" in text_corpus or "mid market" in text_corpus:
        classification = CompanyClassification.MID_SIZE
        evidence.append("Mid-size company signals detected")
        confidence_signals += 0.25
    else:
        classification = CompanyClassification.UNKNOWN
        evidence.append("Insufficient size/funding evidence — classified as UNKNOWN")

    # Normalize confidence to [0.2, 0.95]
    final_confidence = min(max(confidence_signals + 0.3, 0.3), 0.95)

    return CompanyIntelligence(
        company_name=company_name,
        normalized_name=company_name.lower().strip(),
        classification=classification,
        company_type=company_type,
        company_stage=funding_stage or "UNKNOWN",
        employee_count_estimate=employee_count_estimate,
        evidence=evidence,
        confidence=round(final_confidence, 2),
    )
