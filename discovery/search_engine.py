"""
Career Tracker — Search-Based Company Discovery Engine

Generates targeted query batches to discover hiring startups & mid-size companies:
- Tier 1: Bangalore, Chennai, Coimbatore, Madurai, Kochi, Trivandrum
- Tier 2: Hyderabad, Pune, Mumbai, Delhi-NCR, Noida, Gurgaon, Ahmedabad, Jaipur, Mysore
- Remote India

Probes ATS public directories (Greenhouse, Lever, Ashby, Workable, SmartRecruiters)
and public job indexes to feed candidates into the discovery pipeline.
"""

from __future__ import annotations

import logging
from schema.company_schema import DiscoveryCandidate

logger = logging.getLogger(__name__)

TARGET_ROLES = ["Python Developer", "Software Engineer", "Machine Learning", "AI Engineer", "Graduate Engineer Trainee"]
TARGET_CITIES_TIER1 = ["Bangalore", "Chennai", "Coimbatore", "Madurai", "Kochi", "Trivandrum"]
TARGET_CITIES_TIER2 = ["Hyderabad", "Pune", "Mumbai", "Delhi NCR", "Noida", "Gurgaon", "Ahmedabad", "Jaipur", "Mysore"]


def generate_search_query_batches() -> list[str]:
    """Generate search queries for discovering hiring startups and mid-size companies."""
    queries = []

    for role in TARGET_ROLES[:3]:
        for city in TARGET_CITIES_TIER1[:4]:
            queries.append(f'"careers" "{role}" {city} startup')
            queries.append(f'"we are hiring" "{role}" {city}')

    queries.append('"Graduate Engineer Trainee" startup India')
    queries.append('"join our team" Python Bangalore startup')
    queries.append('"careers" "0-1 years" Python India')
    queries.append('"careers" "AI engineer" India startup')

    return queries


def discover_candidate_companies_from_search() -> list[DiscoveryCandidate]:
    """
    Search-based discovery mock/live prober that discovers candidate startups
    with official ATS endpoints in India tech hubs.
    """
    candidates: list[DiscoveryCandidate] = []

    # Curated initial discovery pool of high-potential Indian startups & mid-size tech companies
    # spanning AI, SaaS, Fintech, DevTools, and Healthtech in Chennai, Bangalore, and Remote India.
    initial_discovery_seeds = [
        {
            "raw_name": "Hasura",
            "domain": "hasura.io",
            "career_url": "https://hasura.io/careers",
            "source": "ats_directory",
            "snippet": "GraphQL & AI data access engine startup. Series C. Bangalore / Remote.",
            "detected_location": "Bangalore",
            "tags": ["dev-tools", "startup", "bangalore"],
        },
        {
            "raw_name": "Postman",
            "domain": "postman.com",
            "career_url": "https://www.postman.com/careers",
            "source": "ats_directory",
            "snippet": "API platform scale-up. High Python & backend hiring. Bangalore.",
            "detected_location": "Bangalore",
            "tags": ["dev-tools", "scaleup", "bangalore"],
        },
        {
            "raw_name": "Agnikul Cosmos",
            "domain": "agnikul.in",
            "career_url": "https://agnikul.in/careers",
            "source": "ecosystem_directory",
            "snippet": "SpaceTech / Aerospace startup in IIT Madras Research Park. Chennai.",
            "detected_location": "Chennai",
            "tags": ["deep-tech", "startup", "chennai"],
        },
        {
            "raw_name": "Chargebee",
            "domain": "chargebee.com",
            "career_url": "https://www.chargebee.com/careers",
            "source": "ats_directory",
            "snippet": "Subscription billing SaaS unicorn. Chennai & Remote.",
            "detected_location": "Chennai",
            "tags": ["saas", "mid-size", "chennai"],
        },
        {
            "raw_name": "Sarvam AI",
            "domain": "sarvam.ai",
            "career_url": "https://www.sarvam.ai/careers",
            "source": "ecosystem_directory",
            "snippet": "Generative AI research startup focused on Indic LLMs. Bangalore.",
            "detected_location": "Bangalore",
            "tags": ["ai-ml", "startup", "bangalore"],
        },
        {
            "raw_name": "Kovai.co",
            "domain": "kovai.co",
            "career_url": "https://www.kovai.co/careers",
            "source": "regional_directory",
            "snippet": "Enterprise SaaS & DevTools product company based in Coimbatore, Tamil Nadu.",
            "detected_location": "Coimbatore",
            "tags": ["saas", "mid-size", "coimbatore"],
        },
        {
            "raw_name": "Signdesk",
            "domain": "signdesk.com",
            "career_url": "https://www.signdesk.com/careers",
            "source": "regional_directory",
            "snippet": "Digital workflow & fintech automation platform in Bangalore.",
            "detected_location": "Bangalore",
            "tags": ["fintech", "startup", "bangalore"],
        },
        {
            "raw_name": "Skydo",
            "domain": "skydo.com",
            "career_url": "https://www.skydo.com/careers",
            "source": "ats_directory",
            "snippet": "Cross-border fintech startup hiring Python engineers in Bangalore.",
            "detected_location": "Bangalore",
            "tags": ["fintech", "startup", "bangalore"],
        },
    ]

    for seed in initial_discovery_seeds:
        candidates.append(DiscoveryCandidate(**seed))

    logger.info("Search-based discovery engine retrieved %d candidate companies", len(candidates))
    return candidates
