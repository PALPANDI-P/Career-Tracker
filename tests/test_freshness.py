"""
Tests for the Freshness Engine (Section 6 of MASTER DEVELOPMENT PROMPT).
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from schema.job import Job, SourceType, FreshnessStatus
from dedup.freshness_engine import (
    FreshnessConfig,
    classify_freshness,
    is_notifiable,
    classify_and_update,
    _age_hours,
)


def _make_job(**kwargs) -> Job:
    defaults = dict(
        id="test:123",
        title="Junior Python Developer",
        company="TechCorp",
        url="https://example.com/jobs/1",
        source_type=SourceType.ATS_JSON,
    )
    defaults.update(kwargs)
    return Job(**defaults)


def _ts(hours_ago: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


class TestFreshnessClassification:
    def test_fresh_confirmed_within_24h(self):
        job = _make_job(published_at=_ts(2))  # 2 hours ago
        assert classify_freshness(job) == FreshnessStatus.FRESH_CONFIRMED

    def test_fresh_confirmed_at_threshold(self):
        job = _make_job(published_at=_ts(23.9))
        assert classify_freshness(job) == FreshnessStatus.FRESH_CONFIRMED

    def test_stale_beyond_24h(self):
        job = _make_job(published_at=_ts(25))
        assert classify_freshness(job) == FreshnessStatus.STALE

    def test_stale_much_older(self):
        job = _make_job(published_at=_ts(72))
        assert classify_freshness(job) == FreshnessStatus.STALE

    def test_updated_confirmed(self):
        config = FreshnessConfig(allow_updated_jobs=True)
        job = _make_job(updated_at=_ts(3))  # No published_at, but updated 3h ago
        assert classify_freshness(job, config) == FreshnessStatus.UPDATED_CONFIRMED

    def test_updated_stale_when_disabled(self):
        config = FreshnessConfig(allow_updated_jobs=False)
        job = _make_job(updated_at=_ts(3))
        # No published_at, updated_at disabled => unknown
        assert classify_freshness(job, config) == FreshnessStatus.UNKNOWN

    def test_first_seen_allowed(self):
        config = FreshnessConfig(allow_first_seen_without_publish_date=True)
        job = _make_job(first_seen_at=_ts(1))
        assert classify_freshness(job, config) == FreshnessStatus.FIRST_SEEN

    def test_first_seen_not_allowed_by_default(self):
        config = FreshnessConfig(allow_first_seen_without_publish_date=False)
        job = _make_job(first_seen_at=_ts(1))
        assert classify_freshness(job, config) == FreshnessStatus.UNKNOWN

    def test_unknown_when_no_timestamps(self):
        job = _make_job()
        assert classify_freshness(job) == FreshnessStatus.UNKNOWN

    def test_published_takes_priority_over_updated(self):
        # Even if updated_at is recent, published_at is stale → STALE
        job = _make_job(published_at=_ts(30), updated_at=_ts(1))
        assert classify_freshness(job) == FreshnessStatus.STALE

    def test_posted_date_alias_works(self):
        """posted_date should be treated same as published_at."""
        job = _make_job(posted_date=_ts(5))
        assert classify_freshness(job) == FreshnessStatus.FRESH_CONFIRMED

    def test_custom_max_age(self):
        config = FreshnessConfig(max_age_hours=48)
        job = _make_job(published_at=_ts(36))
        assert classify_freshness(job, config) == FreshnessStatus.FRESH_CONFIRMED


class TestIsNotifiable:
    def test_fresh_confirmed_notifiable(self):
        assert is_notifiable(FreshnessStatus.FRESH_CONFIRMED) is True

    def test_updated_confirmed_notifiable(self):
        assert is_notifiable(FreshnessStatus.UPDATED_CONFIRMED) is True

    def test_stale_not_notifiable(self):
        assert is_notifiable(FreshnessStatus.STALE) is False

    def test_unknown_not_notifiable(self):
        assert is_notifiable(FreshnessStatus.UNKNOWN) is False

    def test_first_seen_depends_on_config(self):
        config_allow = FreshnessConfig(allow_first_seen_without_publish_date=True)
        config_deny = FreshnessConfig(allow_first_seen_without_publish_date=False)
        assert is_notifiable(FreshnessStatus.FIRST_SEEN, config_allow) is True
        assert is_notifiable(FreshnessStatus.FIRST_SEEN, config_deny) is False


class TestClassifyAndUpdate:
    def test_marks_first_seen_at(self):
        job = _make_job()
        assert job.first_seen_at is None
        updated = classify_and_update(job, mark_first_seen=True)
        assert updated.first_seen_at is not None

    def test_does_not_overwrite_first_seen_at(self):
        original_ts = _ts(5)
        job = _make_job(first_seen_at=original_ts)
        updated = classify_and_update(job, mark_first_seen=True)
        # first_seen_at should NOT be overwritten
        assert updated.first_seen_at == original_ts

    def test_freshness_status_updated(self):
        job = _make_job(published_at=_ts(2))
        assert job.freshness_status == FreshnessStatus.UNKNOWN  # Default
        updated = classify_and_update(job)
        assert updated.freshness_status == FreshnessStatus.FRESH_CONFIRMED
