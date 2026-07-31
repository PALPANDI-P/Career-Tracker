"""
Career Tracker — Shared Test Fixtures

Provides reusable sample data for all test modules:
- Sample Job objects (from different ATS types)
- Sample CompanyConfig objects
- Sample profile data
- Temporary database fixtures
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from schema.job import (
    ATSType,
    CompanyConfig,
    Job,
    ScoredJob,
    SeniorityLevel,
    SourceType,
)


# ─── Sample Jobs ──────────────────────────────────


@pytest.fixture
def sample_greenhouse_job() -> Job:
    """A typical job parsed from Greenhouse JSON API."""
    return Job(
        id="cloudflare:4567890",
        external_id="4567890",
        title="Software Engineer, Backend",
        company="Cloudflare",
        location="Austin, TX",
        url="https://boards.greenhouse.io/cloudflare/jobs/4567890",
        description=(
            "We're looking for a backend engineer to help build and scale our "
            "edge computing platform. You'll work with Python, Go, and Rust to "
            "design high-performance distributed systems. Requirements: 2+ years "
            "experience with Python or Go, familiarity with distributed systems, "
            "strong CS fundamentals."
        ),
        department="Engineering",
        seniority_level=SeniorityLevel.MID,
        source_type=SourceType.ATS_JSON,
        ats_type=ATSType.GREENHOUSE,
        posted_date=datetime(2025, 7, 15, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_lever_job() -> Job:
    """A typical job parsed from Lever JSON API."""
    return Job(
        id="netflix:abc123def456",
        external_id="abc123def456",
        title="Senior ML Engineer",
        company="Netflix",
        location="Remote",
        url="https://jobs.lever.co/netflix/abc123def456",
        description=(
            "Join our recommendation team to build next-generation ML models. "
            "You'll design and deploy deep learning pipelines using PyTorch and "
            "TensorFlow. Requirements: 5+ years ML experience, strong Python, "
            "experience with recommendation systems."
        ),
        department="Machine Learning",
        seniority_level=SeniorityLevel.SENIOR,
        source_type=SourceType.ATS_JSON,
        ats_type=ATSType.LEVER,
        posted_date=datetime(2025, 7, 10, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_smartrecruiters_job() -> Job:
    """A typical job parsed from SmartRecruiters API."""
    return Job(
        id="visa:sr-789012",
        external_id="sr-789012",
        title="Junior Data Engineer",
        company="Visa",
        location="San Francisco, CA",
        url="https://jobs.smartrecruiters.com/Visa/sr-789012",
        description=(
            "Entry-level data engineering role building ETL pipelines. "
            "Work with Python, SQL, Apache Spark, and Airflow. "
            "Requirements: BS in CS or related field, familiarity with SQL, "
            "basic Python scripting."
        ),
        department="Data Engineering",
        seniority_level=SeniorityLevel.JUNIOR,
        source_type=SourceType.ATS_JSON,
        ats_type=ATSType.SMARTRECRUITERS,
        posted_date=datetime(2025, 7, 20, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_jobs(
    sample_greenhouse_job: Job,
    sample_lever_job: Job,
    sample_smartrecruiters_job: Job,
) -> list[Job]:
    """Collection of sample jobs from different ATS platforms."""
    return [sample_greenhouse_job, sample_lever_job, sample_smartrecruiters_job]


@pytest.fixture
def sample_scored_job(sample_greenhouse_job: Job) -> ScoredJob:
    """A sample scored job for matcher/notifier tests."""
    return ScoredJob(
        job=sample_greenhouse_job,
        match_score=0.75,
        match_reason="Strong overlap: Python, distributed systems, backend engineering",
    )


# ─── Sample Company Configs ──────────────────────


@pytest.fixture
def sample_greenhouse_config() -> CompanyConfig:
    return CompanyConfig(
        name="Cloudflare",
        careers_url="https://boards.greenhouse.io/cloudflare",
        ats_type=ATSType.GREENHOUSE,
        fetch_strategy="static",
        rate_limit_seconds=2.0,
        enabled=True,
    )


@pytest.fixture
def sample_lever_config() -> CompanyConfig:
    return CompanyConfig(
        name="Netflix",
        careers_url="https://jobs.lever.co/netflix",
        ats_type=ATSType.LEVER,
        fetch_strategy="static",
        rate_limit_seconds=2.0,
        enabled=True,
    )


@pytest.fixture
def sample_company_configs(
    sample_greenhouse_config: CompanyConfig,
    sample_lever_config: CompanyConfig,
) -> list[CompanyConfig]:
    return [sample_greenhouse_config, sample_lever_config]


# ─── Sample Profile ──────────────────────────────


@pytest.fixture
def sample_profile() -> dict:
    """Sample user profile as loaded from YAML."""
    return {
        "target_titles": [
            "Software Engineer",
            "Backend Engineer",
            "ML Engineer",
        ],
        "skills": [
            "Python",
            "JavaScript",
            "Docker",
            "Kubernetes",
            "AWS",
            "PostgreSQL",
            "Machine Learning",
            "PyTorch",
        ],
        "boost_keywords": ["remote", "AI", "machine learning"],
        "penalize_keywords": ["clearance required", "10+ years"],
        "experience_years": 3,
        "target_seniority": ["entry", "junior", "mid"],
        "preferred_locations": ["Remote", "San Francisco, CA", "Austin, TX"],
        "summary": (
            "Software engineer with 3 years of experience in backend development "
            "and growing expertise in machine learning."
        ),
    }


# ─── Temp Directories / DB ──────────────────────


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Temporary database path for dedup store tests."""
    return tmp_path / "test_career_tracker.db"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"
