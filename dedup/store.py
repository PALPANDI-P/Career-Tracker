"""
Career Tracker — Dedup Store

SQLite-backed hash store for deduplicating job listings.
Uses the raw_html_hash from Job objects to track which jobs
have already been seen, so we only notify on genuinely new postings.

This is pure deterministic code — no LLM calls.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from schema.job import Job

logger = logging.getLogger(__name__)


class DedupStore:
    """
    SQLite-backed deduplication store.

    Tracks job hashes to avoid re-processing and re-notifying on
    jobs we've already seen in previous runs.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        """Create a new connection with WAL mode enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except sqlite3.OperationalError:
            pass
        return conn

    def _ensure_db(self) -> None:
        """Create the database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_hashes (
                    hash TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    company TEXT NOT NULL,
                    title TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_seen_company
                ON seen_hashes (company)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_seen_job_id
                ON seen_hashes (job_id)
                """
            )
            conn.commit()

        logger.debug("Dedup store initialized at %s", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        """Create a database connection."""
        return sqlite3.connect(str(self.db_path))

    def is_new(self, job: Job) -> bool:
        """
        Check if a job has been seen before.

        Uses the raw_html_hash for comparison. If the hash is empty
        (no description), falls back to the job ID.

        Returns:
            True if the job is new (not seen before), False otherwise
        """
        lookup_key = job.raw_html_hash or job.id

        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_hashes WHERE hash = ?",
                (lookup_key,),
            ).fetchone()

        return row is None

    def mark_seen(self, job: Job) -> None:
        """
        Record a job as seen in the dedup store.

        Uses INSERT OR IGNORE to handle duplicate inserts gracefully.
        """
        lookup_key = job.raw_html_hash or job.id

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO seen_hashes (hash, job_id, company, title, first_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    lookup_key,
                    job.id,
                    job.company,
                    job.title,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        """
        Filter a list of jobs to only those not seen before.

        Also marks the new jobs as seen in the store.

        Returns:
            List of jobs that are genuinely new
        """
        new_jobs: list[Job] = []

        for job in jobs:
            if self.is_new(job):
                new_jobs.append(job)
                self.mark_seen(job)

        logger.info(
            "Dedup: %d/%d jobs are new",
            len(new_jobs),
            len(jobs),
        )
        return new_jobs

    def count_seen(self, company: str | None = None) -> int:
        """Count total seen jobs, optionally filtered by company."""
        with self._connect() as conn:
            if company:
                row = conn.execute(
                    "SELECT COUNT(*) FROM seen_hashes WHERE company = ?",
                    (company,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM seen_hashes").fetchone()

        return row[0] if row else 0

    def record_run(
        self,
        *,
        companies_processed: int,
        jobs_found: int,
        jobs_new: int,
        errors: list[str] | None = None,
    ) -> int:
        """Record a pipeline run in the runs table."""
        import json

        now = datetime.now(timezone.utc).isoformat()
        errors_json = json.dumps(errors or [])
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    companies_processed INTEGER NOT NULL,
                    jobs_found INTEGER NOT NULL,
                    jobs_new INTEGER NOT NULL,
                    errors TEXT
                )
                """,
            )
            cur = conn.execute(
                """
                INSERT INTO runs (timestamp, companies_processed, jobs_found, jobs_new, errors)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now, companies_processed, jobs_found, jobs_new, errors_json),
            )
            conn.commit()
            return cur.lastrowid

    def clear(self, company: str | None = None) -> int:
        """
        Clear seen hashes, optionally for a specific company.

        Returns the number of records deleted.
        """
        with self._connect() as conn:
            if company:
                cursor = conn.execute(
                    "DELETE FROM seen_hashes WHERE company = ?",
                    (company,),
                )
            else:
                cursor = conn.execute("DELETE FROM seen_hashes")
            conn.commit()
            return cursor.rowcount
