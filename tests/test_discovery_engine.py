"""
Career Tracker — Startup & Mid-Size Company Discovery Engine Unit & Integration Tests

Validates:
1. Evidence-based classification engine (STARTUP_EARLY, STARTUP_GROWTH, MID_SIZE, UNKNOWN)
2. Company name & domain normalization (strips Pvt Ltd, Inc, Private Limited)
3. Official verification gate (rejects third-party job boards, detects ATS types)
4. Scoring & Priority Tier calculations (P0, P1, P2, P3 & feedback loop)
5. Search-based and job-first candidate discovery
6. SQLite discovery store persistence and intelligence querying
"""

from __future__ import annotations

import tempfile
import os
from pathlib import Path

from dedup.store import DedupStore
from discovery.classification_engine import classify_company
from discovery.normalization import normalize_company_name, extract_domain, is_same_company
from discovery.verification import verify_company_candidate, detect_ats_type
from discovery.scoring import (
    calculate_hiring_activity_score,
    calculate_candidate_relevance_score,
    calculate_company_score,
    apply_feedback_adjustment,
)
from discovery.search_engine import discover_candidate_companies_from_search
from discovery.job_first_discovery import discover_company_from_job
from discovery.pipeline import run_company_discovery_pipeline, process_discovery_candidate
from schema.job import Job, JobCategory
from schema.company_schema import CompanyClassification, CompanyPriority, DiscoveryStatus


def test_company_classification():
    intel_early = classify_company("Sarvam AI", raw_snippet="Seed AI research startup", employee_count_estimate=15)
    assert intel_early.classification == CompanyClassification.STARTUP_EARLY
    assert intel_early.company_type.value == "AI_ML"
    assert len(intel_early.evidence) > 0

    intel_mid = classify_company("Chargebee Technologies", raw_snippet="SaaS platform", employee_count_estimate=450)
    assert intel_mid.classification == CompanyClassification.SCALEUP or intel_mid.classification == CompanyClassification.MID_SIZE
    assert intel_mid.company_type.value == "SAAS"

    intel_unknown = classify_company("Generic Company")
    assert intel_unknown.classification == CompanyClassification.UNKNOWN


def test_company_normalization():
    assert normalize_company_name("Hasura Technologies Pvt Ltd") == "hasura"
    assert normalize_company_name("Postman Inc.") == "postman"
    assert normalize_company_name("Chargebee India Private Limited") == "chargebee"

    assert extract_domain("https://jobs.lever.co/atlan") == "lever.co"
    assert extract_domain("https://atlan.com/careers") == "atlan.com"

    assert is_same_company("Hasura Pvt Ltd", "Hasura India", "https://hasura.io", "https://hasura.io/careers") is True


def test_verification_gate():
    # Should reject third-party job aggregator
    status, ats, url, ev = verify_company_candidate("Fake Listing", "indeed.com", "https://indeed.com/viewjob?id=123")
    assert status == DiscoveryStatus.REJECTED

    # Should verify Greenhouse ATS link
    status_gh, ats_gh, url_gh, ev_gh = verify_company_candidate("Atlan", "atlan.com", "https://boards.greenhouse.io/atlan")
    assert status_gh == DiscoveryStatus.VERIFIED
    assert ats_gh == "greenhouse"


def test_scoring_and_priority():
    act_score = calculate_hiring_activity_score(open_roles=10, recent_roles_count=3, fresher_role_count=2)
    assert act_score > 60.0

    rel_score = calculate_candidate_relevance_score(
        job_titles=["Junior Python Developer", "AI Engineer Trainee"],
        fresher_role_count=2,
        locations=["Bangalore"],
    )
    assert rel_score > 70.0

    overall, priority = calculate_company_score(hiring_activity=act_score, candidate_relevance=rel_score)
    assert priority in [CompanyPriority.P0, CompanyPriority.P1]

    # Test feedback loop adjustment
    adjusted = apply_feedback_adjustment(CompanyPriority.P1, total_jobs_seen=10, relevant_matches=6, high_score_matches=4)
    assert adjusted == CompanyPriority.P0


def test_job_first_discovery():
    from schema.job import SourceType
    sample_job = Job(
        id="test:kovai-001",
        source_type=SourceType.HTML_PARSED,
        title="Junior Python Developer",
        company="Kovai.co",
        location="Coimbatore, Tamil Nadu",
        url="https://www.kovai.co/careers/junior-python-dev",
        description="Freshers with Python and MCA degree eligible.",
    )
    cand = discover_company_from_job(sample_job)
    assert cand is not None
    assert cand.raw_name == "Kovai.co"
    assert "coimbatore" in str(cand.detected_location).lower()


def test_discovery_pipeline_and_db_store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        store = DedupStore(db_path)

        summary = run_company_discovery_pipeline(store=store, max_new_companies=10)
        assert summary["total_candidates"] > 0
        assert summary["processed"] > 0

        discovered = store.get_discovered_companies(limit=50)
        assert len(discovered) > 0
        assert "company_name" in discovered[0]
        assert "overall_score" in discovered[0]
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass
