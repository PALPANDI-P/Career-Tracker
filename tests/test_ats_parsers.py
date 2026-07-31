"""
Tests for ATS parsers — Greenhouse, Lever, SmartRecruiters.

Each parser is tested against sample JSON fixtures that mirror
the real API response format.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schema.job import ATSType, SourceType
from extractor.ats_parsers.greenhouse import parse_greenhouse_jobs
from extractor.ats_parsers.lever import parse_lever_jobs
from extractor.ats_parsers.smartrecruiters import parse_smartrecruiters_jobs
from extractor.ats_parsers import get_parser, has_parser, supported_ats_types


FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ─── Greenhouse Parser Tests ────────────────────


class TestGreenhouseParser:
    """Tests for the Greenhouse ATS JSON parser."""

    @pytest.fixture
    def greenhouse_json(self) -> str:
        return (FIXTURES_DIR / "greenhouse_response.json").read_text()

    def test_parses_all_jobs(self, greenhouse_json: str) -> None:
        """Should parse all 3 jobs from the fixture."""
        jobs = parse_greenhouse_jobs(greenhouse_json, "TestCo")
        assert len(jobs) == 3

    def test_job_fields(self, greenhouse_json: str) -> None:
        """Should correctly map Greenhouse fields to Job model."""
        jobs = parse_greenhouse_jobs(greenhouse_json, "TestCo")
        job = jobs[0]

        assert job.title == "Software Engineer, Backend"
        assert job.company == "TestCo"
        assert job.location == "Austin, TX"
        assert job.external_id == "4567890"
        assert str(job.url) == "https://boards.greenhouse.io/testco/jobs/4567890"
        assert job.department == "Engineering"
        assert job.source_type == SourceType.ATS_JSON
        assert job.ats_type == ATSType.GREENHOUSE

    def test_description_html_stripped(self, greenhouse_json: str) -> None:
        """Description should have HTML tags stripped."""
        jobs = parse_greenhouse_jobs(greenhouse_json, "TestCo")
        job = jobs[0]

        assert "<p>" not in job.description
        assert "<li>" not in job.description
        assert "backend engineer" in job.description.lower()

    def test_posted_date_parsed(self, greenhouse_json: str) -> None:
        """Should parse the ISO datetime from updated_at."""
        jobs = parse_greenhouse_jobs(greenhouse_json, "TestCo")
        assert jobs[0].posted_date is not None
        assert jobs[0].posted_date.year == 2025

    def test_job_id_format(self, greenhouse_json: str) -> None:
        """Job ID should follow 'company-slug:external_id' format."""
        jobs = parse_greenhouse_jobs(greenhouse_json, "TestCo")
        assert jobs[0].id == "testco:4567890"

    def test_empty_response(self) -> None:
        """Empty jobs array should return empty list."""
        jobs = parse_greenhouse_jobs('{"jobs": []}', "TestCo")
        assert jobs == []

    def test_no_jobs_key(self) -> None:
        """Missing 'jobs' key should return empty list."""
        jobs = parse_greenhouse_jobs('{"other": "data"}', "TestCo")
        assert jobs == []

    def test_hash_generated(self, greenhouse_json: str) -> None:
        """Each job should have a non-empty raw_html_hash."""
        jobs = parse_greenhouse_jobs(greenhouse_json, "TestCo")
        for job in jobs:
            assert job.raw_html_hash != ""


# ─── Lever Parser Tests ─────────────────────────


class TestLeverParser:
    """Tests for the Lever ATS JSON parser."""

    @pytest.fixture
    def lever_json(self) -> str:
        return (FIXTURES_DIR / "lever_response.json").read_text()

    def test_parses_all_postings(self, lever_json: str) -> None:
        """Should parse all 3 postings from the fixture."""
        jobs = parse_lever_jobs(lever_json, "TestCo")
        assert len(jobs) == 3

    def test_job_fields(self, lever_json: str) -> None:
        """Should correctly map Lever fields to Job model."""
        jobs = parse_lever_jobs(lever_json, "TestCo")
        job = jobs[0]

        assert job.title == "Senior ML Engineer"
        assert job.company == "TestCo"
        assert job.location == "Remote"
        assert job.external_id == "abc123def456"
        assert "lever.co" in str(job.url)
        assert job.department == "Machine Learning"
        assert job.source_type == SourceType.ATS_JSON
        assert job.ats_type == ATSType.LEVER

    def test_description_includes_additional(self, lever_json: str) -> None:
        """Description should include both main and additional text."""
        jobs = parse_lever_jobs(lever_json, "TestCo")
        job = jobs[0]

        assert "recommendation team" in job.description
        assert "Requirements" in job.description

    def test_posted_date_from_timestamp(self, lever_json: str) -> None:
        """Should parse Unix millisecond timestamp."""
        jobs = parse_lever_jobs(lever_json, "TestCo")
        assert jobs[0].posted_date is not None

    def test_job_id_format(self, lever_json: str) -> None:
        """Job ID should use company slug + Lever ID."""
        jobs = parse_lever_jobs(lever_json, "TestCo")
        assert jobs[0].id == "testco:abc123def456"

    def test_empty_array(self) -> None:
        """Empty array should return empty list."""
        jobs = parse_lever_jobs("[]", "TestCo")
        assert jobs == []

    def test_non_list_response(self) -> None:
        """Non-list response should return empty list."""
        jobs = parse_lever_jobs('{"error": "not found"}', "TestCo")
        assert jobs == []


# ─── SmartRecruiters Parser Tests ────────────────


class TestSmartRecruitersParser:
    """Tests for the SmartRecruiters ATS JSON parser."""

    @pytest.fixture
    def sr_json(self) -> str:
        return (FIXTURES_DIR / "smartrecruiters_response.json").read_text()

    def test_parses_all_postings(self, sr_json: str) -> None:
        """Should parse all 2 postings from the fixture."""
        jobs = parse_smartrecruiters_jobs(sr_json, "TestCorp")
        assert len(jobs) == 2

    def test_job_fields(self, sr_json: str) -> None:
        """Should correctly map SmartRecruiters fields to Job model."""
        jobs = parse_smartrecruiters_jobs(sr_json, "TestCorp")
        job = jobs[0]

        assert job.title == "Junior Data Engineer"
        assert job.company == "TestCorp"
        assert "San Francisco" in (job.location or "")
        assert job.department == "Data Engineering"
        assert job.source_type == SourceType.ATS_JSON
        assert job.ats_type == ATSType.SMARTRECRUITERS

    def test_remote_job_location(self, sr_json: str) -> None:
        """Remote job should have 'Remote' as location."""
        jobs = parse_smartrecruiters_jobs(sr_json, "TestCorp")
        remote_job = jobs[1]
        assert remote_job.location == "Remote"

    def test_posted_date_parsed(self, sr_json: str) -> None:
        """Should parse ISO date from releasedDate."""
        jobs = parse_smartrecruiters_jobs(sr_json, "TestCorp")
        assert jobs[0].posted_date is not None
        assert jobs[0].posted_date.year == 2025

    def test_empty_content(self) -> None:
        """Empty content array should return empty list."""
        jobs = parse_smartrecruiters_jobs('{"content": []}', "TestCorp")
        assert jobs == []


# ─── Parser Registry Tests ──────────────────────


class TestParserRegistry:
    """Tests for the ATS parser registry."""

    def test_greenhouse_registered(self) -> None:
        assert has_parser(ATSType.GREENHOUSE)
        assert get_parser(ATSType.GREENHOUSE) is not None

    def test_lever_registered(self) -> None:
        assert has_parser(ATSType.LEVER)
        assert get_parser(ATSType.LEVER) is not None

    def test_smartrecruiters_registered(self) -> None:
        assert has_parser(ATSType.SMARTRECRUITERS)
        assert get_parser(ATSType.SMARTRECRUITERS) is not None

    def test_unknown_not_registered(self) -> None:
        assert not has_parser(ATSType.UNKNOWN)
        assert get_parser(ATSType.UNKNOWN) is None

    def test_supported_types(self) -> None:
        types = supported_ats_types()
        assert ATSType.GREENHOUSE in types
        assert ATSType.LEVER in types
        assert ATSType.SMARTRECRUITERS in types
