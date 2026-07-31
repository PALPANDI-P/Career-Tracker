"""
Tests for the seniority filter — regex-based title classification.
"""

from __future__ import annotations

import pytest

from schema.job import Job, SeniorityLevel, SourceType
from filter.seniority_filter import detect_seniority, filter_by_seniority


def _make_job(title: str) -> Job:
    """Helper to create a minimal Job with just a title."""
    return Job(
        id=f"test:{title.lower().replace(' ', '-')}",
        title=title,
        company="TestCo",
        url="https://example.com/jobs/1",
        source_type=SourceType.ATS_JSON,
    )


class TestDetectSeniority:
    """Tests for seniority level detection from job titles."""

    @pytest.mark.parametrize(
        "title, expected",
        [
            ("Software Engineering Intern", SeniorityLevel.INTERN),
            ("Summer Internship - Engineering", SeniorityLevel.INTERN),
            ("Co-op Developer", SeniorityLevel.INTERN),
            ("Junior Software Engineer", SeniorityLevel.JUNIOR),
            ("Jr. Developer", SeniorityLevel.JUNIOR),
            ("Associate Software Engineer", SeniorityLevel.JUNIOR),
            ("Senior Software Engineer", SeniorityLevel.SENIOR),
            ("Sr. Backend Developer", SeniorityLevel.SENIOR),
            ("Staff Engineer", SeniorityLevel.STAFF),
            ("Principal Engineer", SeniorityLevel.PRINCIPAL),
            ("Distinguished Engineer", SeniorityLevel.PRINCIPAL),
            ("Tech Lead", SeniorityLevel.LEAD),
            ("Team Lead, Backend", SeniorityLevel.LEAD),
            ("Engineering Manager", SeniorityLevel.MANAGER),
            ("Director of Engineering", SeniorityLevel.DIRECTOR),
            ("Head of Platform", SeniorityLevel.DIRECTOR),
            ("VP of Engineering", SeniorityLevel.VP),
            ("Vice President, Technology", SeniorityLevel.VP),
            ("CTO", SeniorityLevel.EXECUTIVE),
            ("Chief Technology Officer", SeniorityLevel.EXECUTIVE),
        ],
    )
    def test_detection(self, title: str, expected: SeniorityLevel) -> None:
        assert detect_seniority(title) == expected

    def test_unknown_for_generic_title(self) -> None:
        """Generic titles without seniority keywords should return UNKNOWN."""
        assert detect_seniority("Software Engineer") == SeniorityLevel.UNKNOWN
        assert detect_seniority("Product Designer") == SeniorityLevel.UNKNOWN

    def test_case_insensitive(self) -> None:
        """Detection should be case-insensitive."""
        assert detect_seniority("SENIOR ENGINEER") == SeniorityLevel.SENIOR
        assert detect_seniority("junior developer") == SeniorityLevel.JUNIOR


class TestFilterBySeniority:
    """Tests for the seniority filtering function."""

    def test_filters_by_target_levels(self) -> None:
        jobs = [
            _make_job("Junior Software Engineer"),
            _make_job("Senior Staff Engineer"),
            _make_job("VP of Engineering"),
            _make_job("Software Engineer"),  # UNKNOWN
        ]
        filtered = filter_by_seniority(
            jobs,
            target_levels=["junior", "mid"],
            include_unknown=False,
        )
        titles = [j.title for j in filtered]
        assert "Junior Software Engineer" in titles
        assert "VP of Engineering" not in titles
        assert "Senior Staff Engineer" not in titles

    def test_include_unknown_default(self) -> None:
        """By default, unknown-seniority jobs should be included."""
        jobs = [
            _make_job("Software Engineer"),  # UNKNOWN
            _make_job("VP of Engineering"),  # VP
        ]
        filtered = filter_by_seniority(
            jobs,
            target_levels=["junior"],
            include_unknown=True,
        )
        titles = [j.title for j in filtered]
        assert "Software Engineer" in titles
        assert "VP of Engineering" not in titles

    def test_empty_target_returns_all(self) -> None:
        """Empty target levels should return all jobs."""
        jobs = [_make_job("Senior Engineer"), _make_job("Junior Dev")]
        filtered = filter_by_seniority(jobs, target_levels=[])
        assert len(filtered) == 2

    def test_no_matching_jobs(self) -> None:
        """Should return empty list if no jobs match."""
        jobs = [_make_job("VP of Engineering"), _make_job("CTO")]
        filtered = filter_by_seniority(
            jobs,
            target_levels=["junior"],
            include_unknown=False,
        )
        assert filtered == []

    def test_all_matching(self) -> None:
        """All jobs matching should all be returned."""
        jobs = [
            _make_job("Junior Developer"),
            _make_job("Jr. Engineer"),
        ]
        filtered = filter_by_seniority(jobs, target_levels=["junior"])
        assert len(filtered) == 2
