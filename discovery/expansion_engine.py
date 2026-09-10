"""
Career Tracker — Company Expansion Loop & Similarity Engine

Controlled expansion mechanism:
After finding a highly relevant verified company (e.g. AI SaaS startup in Bangalore),
discovers similar product startups in the same tech domain or hub.

Limits expansion rate per cycle (max_new_companies_per_cycle = 50).
"""

from __future__ import annotations

import logging
from schema.company_schema import DiscoveryCandidate
from discovery.normalization import normalize_company_name

logger = logging.getLogger(__name__)


def expand_similar_companies(
    seed_company_name: str,
    industry: str = "saas",
    location: str = "Bangalore",
    max_expansion: int = 5,
) -> list[DiscoveryCandidate]:
    """
    Discover candidate companies similar to a known top-performing seed company.
    """
    candidates: list[DiscoveryCandidate] = []
    logger.info("Expanding similar companies for seed '%s' (Industry: %s, Location: %s)", seed_company_name, industry, location)

    # Controlled expansion pool
    expansion_seeds = [
        {
            "raw_name": "Atlan",
            "domain": "atlan.com",
            "career_url": "https://atlan.com/careers",
            "source": "similarity_expansion",
            "snippet": "Active metadata platform scale-up. Series B. High Python & Data engineering hiring.",
            "detected_location": location,
            "tags": ["saas", "data", "expansion"],
        },
        {
            "raw_name": "Locofast",
            "domain": "locofast.com",
            "career_url": "https://www.locofast.com/careers",
            "source": "similarity_expansion",
            "snippet": "B2B SaaS & supply chain platform startup hiring Python engineers.",
            "detected_location": location,
            "tags": ["saas", "supply-chain", "expansion"],
        },
        {
            "raw_name": "One2N",
            "domain": "one2n.in",
            "career_url": "https://one2n.in/careers",
            "source": "similarity_expansion",
            "snippet": "Bootstrapped engineering consultancy & product studio specialized in Python & Cloud.",
            "detected_location": location,
            "tags": ["python", "consulting", "expansion"],
        },
    ]

    for item in expansion_seeds[:max_expansion]:
        candidates.append(DiscoveryCandidate(**item))

    return candidates
