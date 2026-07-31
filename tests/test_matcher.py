"""
Tests for the TF-IDF matcher and matcher package.
"""

from __future__ import annotations

import pytest

from schema.job import Job, ScoredJob, SourceType
from matcher.tfidf_matcher import (
    _build_profile_text,
    _build_job_text,
    _apply_keyword_adjustments,
    score_jobs,
    filter_by_score,
)
from matcher import match_jobs


def _make_job(title: str, description: str, **kwargs) -> Job:
    """Helper to create a minimal Job for testing."""
    return Job(
        id=Job.make_id("TestCo", content=f"{title}-{description}"),
        title=title,
        company="TestCo",
        url="https://example.com/jobs/1",
        description=description,
        source_type=SourceType.ATS_JSON,
        **kwargs,
    )


SAMPLE_PROFILE = {
    "target_titles": ["Software Engineer", "Backend Engineer"],
    "skills": ["Python", "Django", "PostgreSQL", "Docker", "AWS"],
    "boost_keywords": ["remote", "startup"],
    "penalize_keywords": ["clearance required", "10+ years"],
    "summary": "Backend engineer with 3 years Python experience.",
}


class TestBuildProfileText:
    """Tests for profile text construction."""

    def test_includes_titles(self) -> None:
        text = _build_profile_text(SAMPLE_PROFILE)
        assert "Software Engineer" in text

    def test_includes_skills(self) -> None:
        text = _build_profile_text(SAMPLE_PROFILE)
        assert "Python" in text
        assert "Django" in text

    def test_includes_summary(self) -> None:
        text = _build_profile_text(SAMPLE_PROFILE)
        assert "Backend engineer" in text

    def test_empty_profile(self) -> None:
        text = _build_profile_text({})
        assert text == ""


class TestBuildJobText:
    """Tests for job text construction."""

    def test_includes_title_and_description(self) -> None:
        job = _make_job("Backend Engineer", "Build APIs with Python and Django")
        text = _build_job_text(job)
        assert "Backend Engineer" in text
        assert "Python" in text

    def test_includes_department(self) -> None:
        job = _make_job("Engineer", "Build things", department="Platform")
        text = _build_job_text(job)
        assert "Platform" in text


class TestKeywordAdjustments:
    """Tests for boost/penalize keyword adjustments."""

    def test_boost_increases_score(self) -> None:
        job = _make_job("Engineer", "Remote startup opportunity")
        adjusted = _apply_keyword_adjustments(0.5, job, SAMPLE_PROFILE)
        assert adjusted > 0.5  # Both "remote" and "startup" should boost

    def test_penalize_decreases_score(self) -> None:
        job = _make_job("Engineer", "Clearance required, 10+ years experience needed")
        adjusted = _apply_keyword_adjustments(0.5, job, SAMPLE_PROFILE)
        assert adjusted < 0.5

    def test_score_clamped_to_0_1(self) -> None:
        job = _make_job("Engineer", "Remote startup")
        assert 0.0 <= _apply_keyword_adjustments(0.98, job, SAMPLE_PROFILE) <= 1.0
        assert 0.0 <= _apply_keyword_adjustments(0.02, job, {
            "boost_keywords": [],
            "penalize_keywords": ["engineer"],
        }) <= 1.0


class TestScoreJobs:
    """Tests for the main scoring function."""

    def test_returns_scored_jobs(self) -> None:
        jobs = [
            _make_job("Python Backend Engineer", "Build APIs with Python, Django, and PostgreSQL"),
            _make_job("Marketing Manager", "Lead brand campaigns and social media strategy"),
        ]
        scored = score_jobs(jobs, SAMPLE_PROFILE)
        assert len(scored) == 2
        assert all(isinstance(sj, ScoredJob) for sj in scored)

    def test_relevant_job_scores_higher(self) -> None:
        """A job matching the profile should score higher than an unrelated one."""
        jobs = [
            _make_job("Python Backend Engineer", "Build APIs with Python, Django, PostgreSQL on AWS"),
            _make_job("Dental Hygienist", "Clean teeth and perform dental procedures"),
        ]
        scored = score_jobs(jobs, SAMPLE_PROFILE)
        # Sorted by score descending
        assert scored[0].job.title == "Python Backend Engineer"
        assert scored[0].match_score > scored[1].match_score

    def test_sorted_by_score_descending(self) -> None:
        jobs = [
            _make_job("Receptionist", "Answer phones"),
            _make_job("Python Developer", "Python Django REST APIs AWS Docker"),
            _make_job("Data Analyst", "SQL and Excel"),
        ]
        scored = score_jobs(jobs, SAMPLE_PROFILE)
        scores = [sj.match_score for sj in scored]
        assert scores == sorted(scores, reverse=True)

    def test_empty_jobs_list(self) -> None:
        assert score_jobs([], SAMPLE_PROFILE) == []

    def test_match_reason_includes_skills(self) -> None:
        jobs = [
            _make_job("Python Engineer", "Build with Python and Django on Docker"),
        ]
        scored = score_jobs(jobs, SAMPLE_PROFILE)
        assert "Python" in scored[0].match_reason


class TestFilterByScore:
    """Tests for score threshold filtering."""

    def test_filters_below_threshold(self) -> None:
        scored = [
            ScoredJob(job=_make_job("A", "a"), match_score=0.9, match_reason=""),
            ScoredJob(job=_make_job("B", "b"), match_score=0.6, match_reason=""),
            ScoredJob(job=_make_job("C", "c"), match_score=0.3, match_reason=""),
        ]
        kept = filter_by_score(scored, threshold=0.55)
        assert len(kept) == 2

    def test_exact_threshold_included(self) -> None:
        scored = [
            ScoredJob(job=_make_job("A", "a"), match_score=0.55, match_reason=""),
        ]
        kept = filter_by_score(scored, threshold=0.55)
        assert len(kept) == 1


class TestMatchJobs:
    """Tests for the main match_jobs entry point."""

    def test_end_to_end_matching(self) -> None:
        jobs = [
            _make_job("Python Backend Engineer", "Build APIs with Python Django PostgreSQL Docker AWS"),
            _make_job("Dental Hygienist", "Clean teeth and perform dental procedures"),
        ]
        matches = match_jobs(jobs, SAMPLE_PROFILE, threshold_low=0.1)
        assert len(matches) >= 1
        # The Python job should be in the results
        titles = [m.job.title for m in matches]
        assert "Python Backend Engineer" in titles
