"""
Career Tracker — Startup & Mid-Size Company Discovery Pipeline

Coordinates the end-to-end company discovery workflow:
DISCOVERY -> NORMALIZATION -> VERIFICATION -> CLASSIFICATION -> SCORING -> REGISTRY ADDITION -> FULL INVENTORY JOB EXTRACTION

Feeds newly verified companies and their complete job inventory directly into the core monitoring,
deduplication, matching, and notification engine.
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import get_settings
from dedup.store import DedupStore
from discovery.classification_engine import classify_company
from discovery.expansion_engine import expand_similar_companies
from discovery.job_first_discovery import discover_company_from_job
from discovery.normalization import normalize_company_name
from discovery.scoring import (
    calculate_candidate_relevance_score,
    calculate_company_score,
    calculate_hiring_activity_score,
)
from discovery.search_engine import discover_candidate_companies_from_search
from discovery.verification import verify_company_candidate
from schema.company_schema import DiscoveryCandidate, DiscoveryStatus
from schema.job import Job

logger = logging.getLogger(__name__)


def process_discovery_candidate(candidate: DiscoveryCandidate, store: DedupStore) -> dict | None:
    """
    Process a single discovery candidate through verification, classification, scoring, and storage.
    """
    raw_name = candidate.raw_name
    norm_name = normalize_company_name(raw_name)

    if not norm_name:
        return None

    # Step 1: Verification Gate
    status, ats_type, validated_url, verification_evidence = verify_company_candidate(
        company_name=raw_name,
        official_domain=candidate.domain,
        career_url=candidate.career_url,
    )

    if status == DiscoveryStatus.REJECTED:
        logger.info("Candidate '%s' rejected by verification gate", raw_name)
        return None

    # Step 2: Classification Engine
    intel = classify_company(
        company_name=raw_name,
        raw_snippet=candidate.snippet,
        tags=candidate.tags,
    )

    # Step 3: Scoring Engine
    hiring_score = calculate_hiring_activity_score(
        open_roles=3,  # Initial estimate for candidate
        recent_roles_count=1,
        fresher_role_count=1,
    )

    relevance_score = calculate_candidate_relevance_score(
        job_titles=["Software Engineer Trainee", "Junior Python Developer"],
        fresher_role_count=1,
        locations=[candidate.detected_location or "India"],
    )

    overall_score, priority = calculate_company_score(
        hiring_activity=hiring_score,
        candidate_relevance=relevance_score,
    )

    # Merge evidence
    all_evidence = list(set(intel.evidence + verification_evidence))

    company_data = {
        "company_name": raw_name,
        "normalized_name": norm_name,
        "official_domain": candidate.domain,
        "official_career_url": validated_url,
        "company_type": intel.company_type.value,
        "company_size": intel.classification.value,
        "company_stage": intel.company_stage,
        "employee_count_estimate": intel.employee_count_estimate or 0,
        "ats_type": ats_type,
        "ats_url": validated_url,
        "hiring_activity_score": hiring_score,
        "candidate_relevance_score": relevance_score,
        "overall_score": overall_score,
        "priority": priority.value,
        "discovery_source": candidate.source,
        "status": status.value,
        "evidence": all_evidence,
        "confidence": intel.confidence,
    }

    # Persist to SQLite
    company_id = store.save_discovered_company(company_data)
    company_data["id"] = company_id
    logger.info("✅ Saved discovered company '%s' (ID: %d, Priority: %s, Score: %.1f)", raw_name, company_id, priority.value, overall_score)

    return company_data


def run_company_discovery_pipeline(
    store: DedupStore | None = None,
    job_candidates: list[Job] | None = None,
    max_new_companies: int = 50,
) -> dict[str, Any]:
    """
    Run the full company discovery cycle.

    1. Search-Based Company Discovery
    2. Job-First Company Discovery (from input jobs)
    3. Normalization, Verification Gate, Classification, Scoring
    4. Integration with Company Registry & Monitoring
    """
    settings = get_settings()
    target_store = store or DedupStore(settings.db_path)

    logger.info("=" * 65)
    logger.info("🔎 STARTING STARTUP & MID-SIZE COMPANY DISCOVERY PIPELINE")
    logger.info("=" * 65)

    candidates: list[DiscoveryCandidate] = []

    # 1. Search-based discovery candidates
    search_candidates = discover_candidate_companies_from_search()
    candidates.extend(search_candidates)

    # 2. Job-first discovery candidates
    if job_candidates:
        for job in job_candidates[:25]:
            cand = discover_company_from_job(job)
            if cand:
                candidates.append(cand)

    logger.info("Total candidates gathered for processing: %d", len(candidates))

    processed_companies = []
    verified_count = 0
    rejected_count = 0

    for candidate in candidates[:max_new_companies]:
        try:
            result = process_discovery_candidate(candidate, target_store)
            if result:
                processed_companies.append(result)
                if result.get("status") in [DiscoveryStatus.VERIFIED.value, DiscoveryStatus.ACTIVE_HIRING.value]:
                    verified_count += 1
            else:
                rejected_count += 1
        except Exception as e:
            logger.warning("Error processing discovery candidate '%s': %s", candidate.raw_name, e)

    # Summary
    summary = {
        "total_candidates": len(candidates),
        "processed": len(processed_companies),
        "verified": verified_count,
        "rejected": rejected_count,
        "companies": processed_companies[:10],
    }

    logger.info(
        "✅ Company Discovery Pipeline complete: %d candidates -> %d processed, %d verified",
        summary["total_candidates"],
        summary["processed"],
        summary["verified"],
    )

    return summary
