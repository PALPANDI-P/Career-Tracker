"""
Tests for the Job schema — validates the central data contract.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schema.job import (
    ATSType,
    CompanyConfig,
    Job,
    ScoredJob,
    SeniorityLevel,
    SourceType,
)


class TestJobModel:
    """Tests for the core Job Pydantic model."""

    def test_create_valid_job(self) -> None:
        """A well-formed Job should validate without errors."""
        job = Job(
            id="test-co:123",
            external_id="123",
            title="Software Engineer",
            company="Test Co",
            url="https://example.com/jobs/123",
            description="Build great things with Python and React.",
            source_type=SourceType.ATS_JSON,
        )
        assert job.title == "Software Engineer"
        assert job.company == "Test Co"
        assert job.source_type == SourceType.ATS_JSON
        assert job.seniority_level == SeniorityLevel.UNKNOWN
        assert job.raw_html_hash != ""  # auto-generated from description

    def test_empty_title_rejected(self) -> None:
        """Title must not be empty or whitespace-only."""
        with pytest.raises(ValidationError, match="Job title cannot be empty"):
            Job(
                id="x:1",
                title="   ",
                company="Co",
                url="https://example.com/jobs/1",
                source_type=SourceType.ATS_JSON,
            )

    def test_empty_company_rejected(self) -> None:
        """Company must not be empty or whitespace-only."""
        with pytest.raises(ValidationError, match="Company name cannot be empty"):
            Job(
                id="x:1",
                title="Engineer",
                company="  ",
                url="https://example.com/jobs/1",
                source_type=SourceType.ATS_JSON,
            )

    def test_invalid_url_rejected(self) -> None:
        """URL must be a valid HTTP(S) URL."""
        with pytest.raises(ValidationError):
            Job(
                id="x:1",
                title="Engineer",
                company="Co",
                url="not-a-url",
                source_type=SourceType.ATS_JSON,
            )

    def test_hash_auto_generated(self) -> None:
        """raw_html_hash should be auto-generated from description."""
        job = Job(
            id="x:1",
            title="Engineer",
            company="Co",
            url="https://example.com/jobs/1",
            description="Some job description text",
            source_type=SourceType.ATS_JSON,
        )
        assert len(job.raw_html_hash) == 64  # SHA-256 hex

    def test_hash_stable(self) -> None:
        """Same description should produce same hash."""
        desc = "Identical description"
        job1 = Job(
            id="x:1",
            title="E1",
            company="Co",
            url="https://example.com/1",
            description=desc,
            source_type=SourceType.ATS_JSON,
        )
        job2 = Job(
            id="x:2",
            title="E2",
            company="Co",
            url="https://example.com/2",
            description=desc,
            source_type=SourceType.ATS_JSON,
        )
        assert job1.raw_html_hash == job2.raw_html_hash

    def test_hash_not_overwritten_if_provided(self) -> None:
        """If raw_html_hash is explicitly set, don't overwrite it."""
        job = Job(
            id="x:1",
            title="Engineer",
            company="Co",
            url="https://example.com/1",
            description="Some text",
            raw_html_hash="custom-hash-value",
            source_type=SourceType.ATS_JSON,
        )
        assert job.raw_html_hash == "custom-hash-value"

    def test_title_stripped(self) -> None:
        """Title whitespace should be stripped."""
        job = Job(
            id="x:1",
            title="  Software Engineer  ",
            company="Co",
            url="https://example.com/1",
            source_type=SourceType.ATS_JSON,
        )
        assert job.title == "Software Engineer"

    def test_extracted_at_auto_set(self) -> None:
        """extracted_at should default to now (UTC)."""
        job = Job(
            id="x:1",
            title="Engineer",
            company="Co",
            url="https://example.com/1",
            source_type=SourceType.ATS_JSON,
        )
        assert job.extracted_at is not None
        assert job.extracted_at.tzinfo == timezone.utc

    def test_tags_default_empty(self) -> None:
        """Tags should default to empty list."""
        job = Job(
            id="x:1",
            title="Engineer",
            company="Co",
            url="https://example.com/1",
            source_type=SourceType.ATS_JSON,
        )
        assert job.tags == []

    def test_all_source_types(self) -> None:
        """All SourceType enum values should be valid."""
        for st in SourceType:
            job = Job(
                id="x:1",
                title="E",
                company="Co",
                url="https://example.com/1",
                source_type=st,
            )
            assert job.source_type == st


class TestMakeId:
    """Tests for Job.make_id static method."""

    def test_with_external_id(self) -> None:
        """Should use company slug + external ID when available."""
        assert Job.make_id("Cloudflare", external_id="123") == "cloudflare:123"

    def test_with_spaces_in_company(self) -> None:
        """Spaces in company name should become hyphens."""
        assert Job.make_id("Test Company", external_id="456") == "test-company:456"

    def test_without_external_id(self) -> None:
        """Should fall back to content hash when no external ID."""
        id1 = Job.make_id("Acme", content="job description A")
        id2 = Job.make_id("Acme", content="job description B")
        assert id1.startswith("acme:")
        assert id2.startswith("acme:")
        assert id1 != id2  # different content → different hash

    def test_content_hash_deterministic(self) -> None:
        """Same content should always produce same ID."""
        id1 = Job.make_id("Co", content="same content")
        id2 = Job.make_id("Co", content="same content")
        assert id1 == id2


class TestScoredJob:
    """Tests for the ScoredJob model."""

    def test_valid_scored_job(self, sample_greenhouse_job: Job) -> None:
        scored = ScoredJob(
            job=sample_greenhouse_job,
            match_score=0.85,
            match_reason="Strong Python + backend overlap",
        )
        assert scored.match_score == 0.85
        assert scored.llm_judged is False
        assert scored.llm_verdict is None

    def test_score_out_of_range(self, sample_greenhouse_job: Job) -> None:
        """Score must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ScoredJob(
                job=sample_greenhouse_job,
                match_score=1.5,
                match_reason="Too high",
            )

    def test_negative_score_rejected(self, sample_greenhouse_job: Job) -> None:
        with pytest.raises(ValidationError):
            ScoredJob(
                job=sample_greenhouse_job,
                match_score=-0.1,
                match_reason="Negative",
            )


class TestCompanyConfig:
    """Tests for the CompanyConfig model."""

    def test_valid_config(self) -> None:
        config = CompanyConfig(
            name="TestCo",
            careers_url="https://boards.greenhouse.io/testco",
            ats_type=ATSType.GREENHOUSE,
        )
        assert config.fetch_strategy == "static"
        assert config.enabled is True
        assert config.rate_limit_seconds == 2.0

    def test_invalid_strategy_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must be 'static' or 'js'"):
            CompanyConfig(
                name="TestCo",
                careers_url="https://example.com",
                fetch_strategy="magic",
            )

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CompanyConfig(
                name="",
                careers_url="https://example.com",
            )
