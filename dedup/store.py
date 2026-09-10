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
            # ── Discovered Companies Table ───────────
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovered_companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    normalized_name TEXT UNIQUE NOT NULL,
                    official_domain TEXT,
                    official_career_url TEXT,
                    company_type TEXT DEFAULT 'PRODUCT',
                    company_size TEXT DEFAULT 'STARTUP_GROWTH',
                    company_stage TEXT DEFAULT 'UNKNOWN',
                    employee_count_estimate INTEGER DEFAULT 0,
                    ats_type TEXT DEFAULT 'unknown',
                    ats_url TEXT,
                    hiring_activity_score REAL DEFAULT 0.0,
                    candidate_relevance_score REAL DEFAULT 0.0,
                    overall_score REAL DEFAULT 0.0,
                    priority TEXT DEFAULT 'P2',
                    discovery_source TEXT DEFAULT 'search_engine',
                    status TEXT DEFAULT 'DISCOVERED',
                    evidence_json TEXT,
                    confidence REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # ── Company Intelligence Table ────────────
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS company_intelligence (
                    company_id INTEGER PRIMARY KEY,
                    technology_focus TEXT,
                    industry TEXT,
                    engineering_team_signal TEXT,
                    open_role_count INTEGER DEFAULT 0,
                    relevant_role_count INTEGER DEFAULT 0,
                    fresher_role_count INTEGER DEFAULT 0,
                    python_role_count INTEGER DEFAULT 0,
                    ai_ml_role_count INTEGER DEFAULT 0,
                    evidence TEXT,
                    last_updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

        logger.debug("Dedup store initialized at %s", self.db_path)

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

    # ─── Company Discovery Store Methods ─────────────────

    def save_discovered_company(self, company_data: dict) -> int:
        """Insert or update a discovered company entry."""
        import json
        now = datetime.now(timezone.utc).isoformat()
        evidence_str = json.dumps(company_data.get("evidence", []))

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                "SELECT id FROM discovered_companies WHERE normalized_name = ?",
                (company_data["normalized_name"],)
            ).fetchone()

            if existing:
                company_id = existing["id"]
                conn.execute(
                    """
                    UPDATE discovered_companies SET
                        official_domain = COALESCE(?, official_domain),
                        official_career_url = COALESCE(?, official_career_url),
                        ats_type = COALESCE(?, ats_type),
                        ats_url = COALESCE(?, ats_url),
                        hiring_activity_score = ?,
                        candidate_relevance_score = ?,
                        overall_score = ?,
                        priority = ?,
                        status = ?,
                        evidence_json = ?,
                        confidence = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        company_data.get("official_domain"),
                        company_data.get("official_career_url"),
                        company_data.get("ats_type", "unknown"),
                        company_data.get("ats_url"),
                        company_data.get("hiring_activity_score", 0.0),
                        company_data.get("candidate_relevance_score", 0.0),
                        company_data.get("overall_score", 0.0),
                        company_data.get("priority", "P2"),
                        company_data.get("status", "DISCOVERED"),
                        evidence_str,
                        company_data.get("confidence", 0.5),
                        now,
                        company_id,
                    ),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO discovered_companies (
                        company_name, normalized_name, official_domain, official_career_url,
                        company_type, company_size, company_stage, employee_count_estimate,
                        ats_type, ats_url, hiring_activity_score, candidate_relevance_score,
                        overall_score, priority, discovery_source, status, evidence_json,
                        confidence, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company_data["company_name"],
                        company_data["normalized_name"],
                        company_data.get("official_domain"),
                        company_data.get("official_career_url"),
                        company_data.get("company_type", "PRODUCT"),
                        company_data.get("company_size", "STARTUP_GROWTH"),
                        company_data.get("company_stage", "UNKNOWN"),
                        company_data.get("employee_count_estimate", 0),
                        company_data.get("ats_type", "unknown"),
                        company_data.get("ats_url"),
                        company_data.get("hiring_activity_score", 0.0),
                        company_data.get("candidate_relevance_score", 0.0),
                        company_data.get("overall_score", 0.0),
                        company_data.get("priority", "P2"),
                        company_data.get("discovery_source", "search_engine"),
                        company_data.get("status", "DISCOVERED"),
                        evidence_str,
                        company_data.get("confidence", 0.5),
                        now,
                        now,
                    ),
                )
                company_id = cur.lastrowid

            conn.commit()
            return company_id

    def get_discovered_companies(
        self,
        status: str | None = None,
        priority: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch discovered companies with optional status / priority filters."""
        import json
        query = "SELECT * FROM discovered_companies"
        params = []
        conditions = []

        if status and status != "all":
            conditions.append("status = ?")
            params.append(status)
        if priority and priority != "all":
            conditions.append("priority = ?")
            params.append(priority)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY overall_score DESC, id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            try:
                d["evidence"] = json.loads(d.get("evidence_json") or "[]")
            except Exception:
                d["evidence"] = []
            results.append(d)
        return results

