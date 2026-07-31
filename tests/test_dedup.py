"""
Tests for the dedup store — SQLite-backed hash deduplication.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from schema.job import Job, SourceType
from dedup.store import DedupStore


def _make_job(title: str, description: str = "test desc", company: str = "TestCo") -> Job:
    """Helper to create a minimal Job for testing."""
    return Job(
        id=Job.make_id(company, content=f"{title}-{description}"),
        title=title,
        company=company,
        url="https://example.com/jobs/1",
        description=description,
        source_type=SourceType.ATS_JSON,
    )


class TestDedupStore:
    """Tests for the DedupStore class."""

    @pytest.fixture
    def store(self, tmp_db_path: Path) -> DedupStore:
        """Create a fresh dedup store with a temp database."""
        return DedupStore(tmp_db_path)

    def test_new_job_is_new(self, store: DedupStore) -> None:
        """A job never seen before should be detected as new."""
        job = _make_job("Engineer")
        assert store.is_new(job) is True

    def test_seen_job_not_new(self, store: DedupStore) -> None:
        """A job that has been marked seen should no longer be new."""
        job = _make_job("Engineer")
        store.mark_seen(job)
        assert store.is_new(job) is False

    def test_different_jobs_are_independent(self, store: DedupStore) -> None:
        """Different jobs should be tracked independently."""
        job1 = _make_job("Engineer", description="build things")
        job2 = _make_job("Designer", description="design things")

        store.mark_seen(job1)
        assert store.is_new(job1) is False
        assert store.is_new(job2) is True

    def test_filter_new_returns_only_new(self, store: DedupStore) -> None:
        """filter_new should return only unseen jobs and mark them."""
        job1 = _make_job("Engineer", description="desc1")
        job2 = _make_job("Designer", description="desc2")
        job3 = _make_job("Manager", description="desc3")

        store.mark_seen(job1)

        new_jobs = store.filter_new([job1, job2, job3])
        assert len(new_jobs) == 2
        assert job2 in new_jobs
        assert job3 in new_jobs

        # After filtering, all should be seen
        assert store.is_new(job2) is False
        assert store.is_new(job3) is False

    def test_count_seen(self, store: DedupStore) -> None:
        """count_seen should return the correct count."""
        assert store.count_seen() == 0

        store.mark_seen(_make_job("E1", description="d1"))
        store.mark_seen(_make_job("E2", description="d2"))
        assert store.count_seen() == 2

    def test_count_seen_by_company(self, store: DedupStore) -> None:
        """count_seen should filter by company when specified."""
        store.mark_seen(_make_job("E1", description="d1", company="Alpha"))
        store.mark_seen(_make_job("E2", description="d2", company="Beta"))
        store.mark_seen(_make_job("E3", description="d3", company="Alpha"))

        assert store.count_seen("Alpha") == 2
        assert store.count_seen("Beta") == 1
        assert store.count_seen() == 3

    def test_clear_all(self, store: DedupStore) -> None:
        """clear should remove all records."""
        store.mark_seen(_make_job("E1", description="d1"))
        store.mark_seen(_make_job("E2", description="d2"))

        deleted = store.clear()
        assert deleted == 2
        assert store.count_seen() == 0

    def test_clear_by_company(self, store: DedupStore) -> None:
        """clear should remove only the specified company's records."""
        store.mark_seen(_make_job("E1", description="d1", company="Alpha"))
        store.mark_seen(_make_job("E2", description="d2", company="Beta"))

        deleted = store.clear("Alpha")
        assert deleted == 1
        assert store.count_seen() == 1

    def test_mark_seen_idempotent(self, store: DedupStore) -> None:
        """Marking the same job as seen twice should not error."""
        job = _make_job("Engineer")
        store.mark_seen(job)
        store.mark_seen(job)  # Should not raise
        assert store.count_seen() == 1

    def test_persistence_across_instances(self, tmp_db_path: Path) -> None:
        """Data should persist across DedupStore instances (same DB file)."""
        store1 = DedupStore(tmp_db_path)
        job = _make_job("Engineer")
        store1.mark_seen(job)

        store2 = DedupStore(tmp_db_path)
        assert store2.is_new(job) is False

    def test_record_run_returns_run_id(self, store: DedupStore) -> None:
        run_id = store.record_run(
            companies_processed=3,
            jobs_found=10,
            jobs_new=2,
        )
        assert isinstance(run_id, int)
        assert run_id > 0

    def test_record_run_stores_correct_values(self, store: DedupStore) -> None:
        errors = ["Alpha: timeout"]
        run_id = store.record_run(
            companies_processed=3,
            jobs_found=10,
            jobs_new=2,
            errors=errors,
        )

        conn = sqlite3.connect(str(store.db_path))
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        conn.close()

        assert row is not None
        # columns: run_id, timestamp, companies_processed, jobs_found, jobs_new, errors
        assert row[1] is not None  # timestamp is not null
        assert row[2] == 3  # companies_processed
        assert row[3] == 10  # jobs_found
        assert row[4] == 2  # jobs_new
        assert "Alpha" in row[5]  # errors JSON

    def test_record_run_empty_errors(self, store: DedupStore) -> None:
        run_id = store.record_run(
            companies_processed=1,
            jobs_found=0,
            jobs_new=0,
            errors=[],
        )
        conn = sqlite3.connect(str(store.db_path))
        row = conn.execute("SELECT errors FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        conn.close()
        assert row is not None
