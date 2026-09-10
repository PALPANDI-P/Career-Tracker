"""
Career Tracker — Company Intelligence & Discovery Schemas

Pydantic models for company classification, evidence tracking,
hiring activity scoring, and discovery candidate records.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, HttpUrl


class CompanyClassification(str, Enum):
    STARTUP_EARLY = "STARTUP_EARLY"       # Seed / Early stage (< 50 employees)
    STARTUP_GROWTH = "STARTUP_GROWTH"     # Series A/B/C growing startup (50-200)
    SCALEUP = "SCALEUP"                   # Scale-up / Late stage startup (200-500)
    MID_SIZE = "MID_SIZE"                 # Mid-size product/SaaS company (100-1000)
    LARGE = "LARGE"                       # Established large enterprise (> 1000)
    ENTERPRISE = "ENTERPRISE"             # Big tech / Global MNC
    UNKNOWN = "UNKNOWN"                   # Insufficient evidence


class CompanyType(str, Enum):
    PRODUCT = "PRODUCT"
    SAAS = "SAAS"
    AI_ML = "AI_ML"
    FINTECH = "FINTECH"
    HEALTHTECH = "HEALTHTECH"
    EDTECH = "EDTECH"
    DEV_TOOLS = "DEV_TOOLS"
    CYBERSECURITY = "CYBERSECURITY"
    SERVICES = "SERVICES"
    OTHER = "OTHER"


class DiscoveryStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    ACTIVE_HIRING = "ACTIVE_HIRING"
    LOW_ACTIVITY = "LOW_ACTIVITY"
    NO_CAREER_PAGE = "NO_CAREER_PAGE"
    SOURCE_FAILED = "SOURCE_FAILED"
    DORMANT = "DORMANT"
    REJECTED = "REJECTED"


class CompanyPriority(str, Enum):
    P0 = "P0"   # Highly relevant + active hiring (30m refresh)
    P1 = "P1"   # Relevant + active hiring (60m refresh)
    P2 = "P2"   # Moderate relevance (2-4h refresh)
    P3 = "P3"   # Low activity / low relevance (daily refresh)


class CompanyIntelligence(BaseModel):
    """Rich intelligence profile and evidence breakdown for a company."""
    company_name: str
    normalized_name: str
    official_domain: Optional[str] = None
    official_career_url: Optional[str] = None
    ats_type: str = "unknown"
    ats_url: Optional[str] = None

    classification: CompanyClassification = CompanyClassification.UNKNOWN
    company_type: CompanyType = CompanyType.PRODUCT
    company_stage: Optional[str] = None
    employee_count_estimate: Optional[int] = None

    hiring_activity_score: float = Field(default=0.0, ge=0.0, le=100.0)
    candidate_relevance_score: float = Field(default=0.0, ge=0.0, le=100.0)
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0)
    priority: CompanyPriority = CompanyPriority.P2

    open_role_count: int = 0
    fresher_role_count: int = 0
    python_role_count: int = 0
    ai_ml_role_count: int = 0
    backend_role_count: int = 0

    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    discovery_source: str = "search_engine"
    status: DiscoveryStatus = DiscoveryStatus.DISCOVERED


class DiscoveryCandidate(BaseModel):
    """A raw company candidate found during discovery before verification."""
    raw_name: str
    domain: Optional[str] = None
    career_url: Optional[str] = None
    source: str
    snippet: Optional[str] = None
    detected_location: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
