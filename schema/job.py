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
from typing import Optional

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
    SMARTRECRUITERS = "smartrecruiters"
    CUSTOM = "custom"
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
    """

    # --- Identity ---
    id: str = Field(
        ...,
        description="Unique identifier: '{company}:{external_id}' or '{company}:{hash}'",
    )
    external_id: Optional[str] = Field(
        default=None,
        description="The job ID from the source ATS (e.g., Greenhouse job ID)",
    )

    # --- Core Fields ---
    title: str = Field(..., min_length=1, description="Job title")
    company: str = Field(..., min_length=1, description="Company name")
    location: Optional[str] = Field(default=None, description="Job location or 'Remote'")
    url: HttpUrl = Field(..., description="Direct link to the job posting")
    description: str = Field(default="", description="Full job description text")
    department: Optional[str] = Field(default=None, description="Department or team name")

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

    # --- Metadata ---
    posted_date: Optional[datetime] = Field(
        default=None,
        description="When the job was posted (if available from source)",
    )
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When we extracted this job",
    )
    raw_html_hash: str = Field(
        default="",
        description="SHA-256 hash of the raw source content for dedup",
    )

    # --- India-Specific Fields ---
    region: Optional[str] = Field(
        default=None,
        description="Region: 'tamil_nadu', 'karnataka', 'global', etc.",
    )
    city: Optional[str] = Field(
        default=None,
        description="Specific city: Chennai, Bangalore, Coimbatore, etc.",
    )
    experience_required: Optional[str] = Field(
        default=None,
        description="Experience range: '0-1 years', '1-3 years', etc.",
    )
    is_fresher_eligible: bool = Field(
        default=False,
        description="Whether the job is explicitly marked as fresher/training eligible",
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
        description="Arbitrary tags (e.g., 'remote', 'visa-sponsor')",
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
    def ensure_hash(self) -> "Job":
        """Generate raw_html_hash from description if not already set."""
        if not self.raw_html_hash and self.description:
            self.raw_html_hash = hashlib.sha256(
                self.description.encode("utf-8")
            ).hexdigest()
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

    @field_validator("fetch_strategy")
    @classmethod
    def valid_strategy(cls, v: str) -> str:
        if v not in ("static", "js"):
            raise ValueError(f"fetch_strategy must be 'static' or 'js', got '{v}'")
        return v
