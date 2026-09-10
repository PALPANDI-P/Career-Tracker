"""
Career Tracker — Shared Job Schema

The Job model is the central contract for the entire pipeline.
Every module (fetcher, extractor, matcher, notifier) reads and writes Job objects.
This is what makes modules independently testable and safely editable by agents.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class SourceType(str, Enum):
    """How the job data was extracted."""

    ATS_JSON = "ats_json"
    HTML_PARSED = "html_parsed"
    LLM_EXTRACTED = "llm_extracted"


class ATSType(str, Enum):
    """Known ATS platforms with structured APIs."""

    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKABLE = "workable"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"
    WORKDAY = "workday"
    RSS = "rss"
    SITEMAP = "sitemap"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class FreshnessStatus(str, Enum):
    """Freshness classification per Section 6 of MASTER DEVELOPMENT PROMPT."""

    FRESH_CONFIRMED = "fresh_confirmed"       # Published <= 24h ago (official timestamp)
    UPDATED_CONFIRMED = "updated_confirmed"   # Updated <= 24h ago (official timestamp)
    FIRST_SEEN = "first_seen"                 # New to our system, no official publish date
    STALE = "stale"                           # Older than max_age_hours
    UNKNOWN = "unknown"                       # Insufficient timestamp data


class LifecycleStatus(str, Enum):
    """Job lifecycle state machine per Section 8 of MASTER DEVELOPMENT PROMPT."""

    DISCOVERED = "discovered"
    NORMALIZED = "normalized"
    VALIDATED = "validated"
    FRESHNESS_CHECK = "freshness_check"
    DUPLICATE_CHECK = "duplicate_check"
    ELIGIBILITY_FILTER = "eligibility_filter"
    AI_MATCHING = "ai_matching"
    RANKED = "ranked"
    NOTIFIED = "notified"
    SAVED = "saved"
    APPLICATION_STARTED = "application_started"
    APPLIED = "applied"
    ASSESSMENT = "assessment"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"
    JOINED = "joined"
    CLOSED_OR_REMOVED = "closed_or_removed"


class RemoteType(str, Enum):
    """Work arrangement type."""

    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE_INDIA = "remote_india"
    REMOTE_WORLDWIDE = "remote_worldwide"
    UNKNOWN = "unknown"


class SeniorityLevel(str, Enum):
    """Standardized seniority levels for filtering."""

    INTERN = "intern"
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    VP = "vp"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class JobCategory(str, Enum):
    """Category of the job posting, especially for Indian IT market."""

    FRESHER = "fresher"
    TRAINING = "training"
    INTERNSHIP = "internship"
    JUNIOR = "junior"
    LATERAL = "lateral"
    WALK_IN = "walk_in"
    CAMPUS = "campus"
    UNKNOWN = "unknown"


class NotificationPriority(str, Enum):
    """Priority level for dashboard color-coded notifications."""

    URGENT = "urgent"        # 🔴 Red flash — walk-in / limited deadline
    HOT = "hot"              # 🟢 Green glow — score ≥ 80% AND fresher-eligible
    GOOD = "good"            # 🔵 Blue glow — score ≥ 65%
    WORTH_CHECKING = "worth_checking"  # 🟡 Yellow glow — score 55–65%
    NEW = "new"              # 🟣 Purple pulse — new posting, any score
    NORMAL = "normal"        # Default


class Job(BaseModel):
    """
    The central data contract for the career tracker pipeline.

    Every module in the system — fetcher, extractor, dedup, matcher, filter,
    notifier — communicates through Job objects. This is the single shared
    schema that keeps module boundaries clean.

    Fields normalized per Section 5 of the MASTER DEVELOPMENT PROMPT.
    """

    # --- Identity (Section 5: job_id, source, source_job_id, company_id) ---
    id: str = Field(
        ...,
        description="Unique identifier: '{company}:{external_id}' or '{company}:{hash}'",
    )
    source: Optional[str] = Field(
        default=None,
        description="Source identifier (e.g. 'greenhouse', 'lever', 'rss')",
    )
    source_job_id: Optional[str] = Field(
        default=None,
        description="The job ID from the source ATS (e.g., Greenhouse job ID)",
    )
    external_id: Optional[str] = Field(
        default=None,
        description="Alias for source_job_id (backwards compat)",
    )
    company_id: Optional[str] = Field(
        default=None,
        description="Internal company registry ID",
    )

    # --- Core Normalized Fields (Section 5) ---
    title: str = Field(..., min_length=1, description="Job title")
    company: str = Field(..., min_length=1, description="Company name")
    location: Optional[str] = Field(default=None, description="Raw location string from source")
    canonical_location: Optional[str] = Field(
        default=None,
        description="Normalized location: 'City, State, Country' canonical form",
    )
    url: HttpUrl = Field(..., description="Source URL of the job posting")
    application_url: Optional[str] = Field(
        default=None,
        description="Official application URL (cleaned, validated)",
    )
    source_url: Optional[str] = Field(
        default=None,
        description="Original raw source URL (before cleaning)",
    )
    canonical_url: Optional[str] = Field(
        default=None,
        description="Canonical de-tracked application URL",
    )
    description: str = Field(default="", description="Full job description text")
    department: Optional[str] = Field(default=None, description="Department or team name")
    employment_type: Optional[str] = Field(
        default=None,
        description="Full-time, Part-time, Contract, Internship, etc.",
    )
    experience_text: Optional[str] = Field(
        default=None,
        description="Raw experience requirement text from the JD (e.g. '0-1 years')",
    )
    education_text: Optional[str] = Field(
        default=None,
        description="Raw education requirement text from the JD (e.g. 'B.E/B.Tech/MCA')",
    )
    salary_text: Optional[str] = Field(
        default=None,
        description="Salary or CTC text if available from source",
    )
    skills: List[str] = Field(
        default_factory=list,
        description="Skills extracted from job description",
    )
    remote_type: RemoteType = Field(
        default=RemoteType.UNKNOWN,
        description="Work arrangement: onsite, hybrid, remote_india, remote_worldwide",
    )

    # --- Classification ---
    seniority_level: SeniorityLevel = Field(
        default=SeniorityLevel.UNKNOWN,
        description="Detected seniority level (from title parsing or LLM)",
    )
    source_type: SourceType = Field(
        ...,
        description="How this job was extracted",
    )
    ats_type: ATSType = Field(
        default=ATSType.UNKNOWN,
        description="Which ATS platform this came from",
    )

    # --- Timestamps (Section 6 freshness priority chain) ---
    published_at: Optional[datetime] = Field(
        default=None,
        description="Official publish timestamp from ATS (highest priority)",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Official last-updated timestamp from ATS",
    )
    first_seen_at: Optional[datetime] = Field(
        default=None,
        description="When this system first discovered the job (lowest priority fallback)",
    )
    last_seen_at: Optional[datetime] = Field(
        default=None,
        description="Last time the job was confirmed still live",
    )
    # Keep posted_date for backwards compatibility
    posted_date: Optional[datetime] = Field(
        default=None,
        description="Alias for published_at (backwards compatibility)",
    )
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When we extracted this job from the source",
    )

    # --- URL validation (Section 20) ---
    url_checked_at: Optional[datetime] = Field(
        default=None,
        description="When the application URL was last validated",
    )
    url_status: Optional[str] = Field(
        default=None,
        description="HTTP status or result of last URL validation",
    )

    # --- Dedup (Sections 5, 7) ---
    raw_html_hash: str = Field(
        default="",
        description="SHA-256 of raw source content for dedup",
    )
    content_hash: Optional[str] = Field(
        default=None,
        description="SHA-256(normalized_title+company+description+location) for dedup",
    )

    # --- Freshness Classification (Section 6) ---
    freshness_status: FreshnessStatus = Field(
        default=FreshnessStatus.UNKNOWN,
        description="Freshness classification: FRESH_CONFIRMED, UPDATED_CONFIRMED, FIRST_SEEN, STALE, UNKNOWN",
    )

    # --- Lifecycle State Machine (Section 8) ---
    lifecycle_status: LifecycleStatus = Field(
        default=LifecycleStatus.DISCOVERED,
        description="Current stage of the job in the pipeline lifecycle",
    )

    # --- Matching & Scoring (Section 13-18) ---
    overall_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Hybrid overall match score 0-100",
    )
    matched_skills: List[str] = Field(
        default_factory=list,
        description="Skills matched between job and candidate profile",
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Skills in JD that candidate does not have",
    )
    recommended_resume: Optional[str] = Field(
        default=None,
        description="Selected resume variant filename for this job",
    )
    recruiter_keyword_coverage: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Recruiter keyword reachability coverage % (Section 43)",
    )
    matched_project: Optional[str] = Field(
        default=None,
        description="Most relevant candidate project name for this job",
    )
    project_relevance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Candidate project relevance score for this job",
    )

    # --- India-Specific Fields ---
    region: Optional[str] = Field(
        default=None,
        description="Region: 'tamil_nadu', 'karnataka', 'global', etc.",
    )
    city: Optional[str] = Field(
        default=None,
        description="Canonical city: Chennai, Bangalore, Coimbatore, etc.",
    )
    state: Optional[str] = Field(
        default=None,
        description="Canonical state: Tamil Nadu, Karnataka, Kerala, etc.",
    )
    country: Optional[str] = Field(
        default=None,
        description="Country (e.g. India)",
    )
    experience_required: Optional[str] = Field(
        default=None,
        description="Experience range: '0-1 years', '1-3 years', etc.",
    )
    is_fresher_eligible: bool = Field(
        default=False,
        description="Whether the job is explicitly marked as fresher/training eligible",
    )
    fresher_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score of fresher eligibility detection (0-1)",
    )
    job_category: JobCategory = Field(
        default=JobCategory.UNKNOWN,
        description="Category: fresher, training, internship, lateral, etc.",
    )
    notification_priority: NotificationPriority = Field(
        default=NotificationPriority.NORMAL,
        description="Priority for dashboard color-coded notifications",
    )

    # --- Tags (for extensibility) ---
    tags: list[str] = Field(
        default_factory=list,
        description="Arbitrary tags (e.g., 'remote', 'walk-in', 'startup')",
    )

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Job title cannot be empty or whitespace-only")
        return stripped

    @field_validator("company")
    @classmethod
    def company_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Company name cannot be empty or whitespace-only")
        return stripped

    @model_validator(mode="after")
    def ensure_hashes(self) -> "Job":
        """Generate raw_html_hash and content_hash if not already set."""
        # SHA-256 of raw description content
        if not self.raw_html_hash and self.description:
            self.raw_html_hash = hashlib.sha256(
                self.description.encode("utf-8")
            ).hexdigest()

        # Canonical content hash: SHA-256(title+company+description+location)
        # Used as fallback dedup key per Section 7
        if not self.content_hash:
            dedup_str = "|".join([
                (self.title or "").strip().lower(),
                (self.company or "").strip().lower(),
                (self.description or "")[:2000].strip().lower(),
                (self.canonical_location or self.location or "").strip().lower(),
            ])
            self.content_hash = hashlib.sha256(dedup_str.encode("utf-8")).hexdigest()

        # Propagate published_at <-> posted_date for backwards compat
        if not self.published_at and self.posted_date:
            self.published_at = self.posted_date
        elif not self.posted_date and self.published_at:
            self.posted_date = self.published_at

        # Propagate source_job_id <-> external_id
        if not self.source_job_id and self.external_id:
            self.source_job_id = self.external_id
        elif not self.external_id and self.source_job_id:
            self.external_id = self.source_job_id

        return self

    @staticmethod
    def make_id(company: str, external_id: str | None = None, content: str = "") -> str:
        """
        Generate a stable job ID.

        Uses external ATS ID when available, falls back to content hash.
        """
        company_slug = company.lower().strip().replace(" ", "-")
        if external_id:
            return f"{company_slug}:{external_id}"
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        return f"{company_slug}:{content_hash}"

    @staticmethod
    def make_content_hash(
        title: str,
        company: str,
        description: str = "",
        location: str = "",
    ) -> str:
        """Generate canonical content hash per Section 7 of MASTER DEVELOPMENT PROMPT."""
        dedup_str = "|".join([
            title.strip().lower(),
            company.strip().lower(),
            description[:2000].strip().lower(),
            location.strip().lower(),
        ])
        return hashlib.sha256(dedup_str.encode("utf-8")).hexdigest()


class ScoredJob(BaseModel):
    """A Job with match scoring metadata, produced by the matcher module."""

    job: Job
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="TF-IDF cosine similarity score (0–1)",
    )
    match_reason: str = Field(
        default="",
        description="Human-readable explanation of why this matched",
    )
    llm_judged: bool = Field(
        default=False,
        description="Whether an LLM was used for borderline judgment",
    )
    llm_verdict: Optional[str] = Field(
        default=None,
        description="LLM's reasoning if it was consulted",
    )


class CompanyConfig(BaseModel):
    """Configuration for a single company's career page."""

    model_config = {"extra": "ignore"}  # silently ignore unknown YAML keys

    name: str = Field(..., min_length=1)
    careers_url: HttpUrl
    fresher_careers_url: Optional[HttpUrl] = Field(
        default=None,
        description="Direct link to company's dedicated fresher / trainee / campus recruitment portal",
    )
    fresher_role_types: list[str] = Field(
        default_factory=list,
        description="Specific fresher & trainee role titles recruited by this company",
    )
    ats_type: ATSType = Field(default=ATSType.UNKNOWN)
    ats_identifier: Optional[str] = Field(
        default=None,
        description="ATS board slug/identifier when different from careers_url slug",
    )
    fetch_strategy: str = Field(
        default="static",
        description="'static' for requests, 'js' for Playwright",
    )
    custom_selectors: Optional[dict[str, str]] = Field(
        default=None,
        description="CSS selectors for custom HTML parsing",
    )
    rate_limit_seconds: float = Field(
        default=2.0,
        ge=0.0,
        description="Delay between requests to this company's domain",
    )
    enabled: bool = Field(default=True, description="Whether to include in pipeline runs")
    location_filter: Optional[str] = Field(
        default=None,
        description="Geographic filter hint (e.g. 'Tamil Nadu', 'India', 'global')",
    )
    target_levels: list[str] = Field(
        default_factory=list,
        description="Seniority levels this company recruits for (e.g. ['fresher', 'junior'])",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Arbitrary tags for this company (e.g. 'mnc', 'data-role', 'tamil-nadu')",
    )

    @field_validator("fetch_strategy")
    @classmethod
    def valid_strategy(cls, v: str) -> str:
        if v not in ("static", "js"):
            raise ValueError(f"fetch_strategy must be 'static' or 'js', got '{v}'")
        return v
