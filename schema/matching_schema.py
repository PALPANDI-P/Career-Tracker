"""
Matching & AI Evaluation Schemas

Defines Pydantic schemas for LLM evaluation, hybrid score breakdowns,
and application preparation content.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class LLMMatchResult(BaseModel):
    """Structured output returned by the LLM evaluation agent."""

    overall_score: float = Field(..., ge=0, le=100, description="Overall match percentage 0-100")
    role_match: float = Field(default=0, ge=0, le=100, description="Role taxonomy alignment")
    skill_match: float = Field(default=0, ge=0, le=100, description="Skill matrix alignment")
    experience_match: float = Field(default=0, ge=0, le=100, description="Seniority / experience alignment")
    education_match: float = Field(default=0, ge=0, le=100, description="Education degree alignment (MCA/BCA)")
    location_match: float = Field(default=0, ge=0, le=100, description="Geographic preference score")
    project_match: float = Field(default=0, ge=0, le=100, description="Candidate project alignment score")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Model confidence score")
    recommendation: str = Field(
        default="REVIEW",
        description="HIGH_PRIORITY, STRONG_MATCH, REVIEW, or DO_NOT_NOTIFY",
    )
    matched_skills: List[str] = Field(default_factory=list, description="Skills present in candidate profile")
    missing_skills: List[str] = Field(default_factory=list, description="Skills missing in candidate profile")
    matched_project: Optional[str] = Field(default=None, description="Most relevant candidate project name")
    project_relevance_score: float = Field(default=0.0, ge=0, le=100)
    recruiter_keyword_coverage: float = Field(default=0.0, ge=0, le=100)
    reason: str = Field(default="", description="Detailed human-readable explanation of fit")
    risk_flags: List[str] = Field(default_factory=list, description="Any risk factors or caveats")


class ApplicationPack(BaseModel):
    """Prepared application materials grounded strictly in candidate profile."""

    job_id: str = Field(...)
    company_name: str = Field(...)
    job_title: str = Field(...)
    recommended_resume: str = Field(..., description="Selected resume filename")
    short_application_message: str = Field(..., description="Brief candidate introduction message")
    cover_letter: str = Field(..., description="Full cover letter tailored to the job")
    skill_summary: List[str] = Field(default_factory=list, description="Key skills highlighted for this job")
    project_relevance: str = Field(..., description="Explanation of how candidate project aligns")
    common_application_answers: dict[str, str] = Field(
        default_factory=dict,
        description="Prepared answers for standard ATS questions (e.g. notice period, degree, location)",
    )
    official_application_url: str = Field(...)
