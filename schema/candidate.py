"""
Candidate Profile, Resume, and Project Schemas

Defines configurable candidate profile, resume variants metadata, and candidate projects.
"""

from __future__ import annotations

from typing import List, Dict, Optional
from pydantic import BaseModel, Field, HttpUrl


class EducationEntry(BaseModel):
    degree: str = Field(..., description="Degree title (e.g., MCA, BCA)")
    university: str = Field(..., description="University / Institution name")
    period: str = Field(..., description="Duration or year of completion (e.g. 2026)")


class ResumeVariant(BaseModel):
    role: str = Field(..., description="Target role name (e.g. Python Developer)")
    file: str = Field(..., description="Filename of resume (e.g. PALPANDI_P_Resume_Python_Developer.pdf)")
    cities: List[str] = Field(default_factory=list, description="Target cities for this resume variant")
    active: bool = Field(default=True)


class CandidateProject(BaseModel):
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="Brief summary of project")
    technologies: List[str] = Field(default_factory=list, description="List of tech stacks / skills used")


class LocationWeights(BaseModel):
    preferred_city: float = Field(default=1.0)
    preferred_state: float = Field(default=0.9)
    remote: float = Field(default=0.9)
    india_other: float = Field(default=0.5)
    outside_india: float = Field(default=0.0)


class CandidateProfile(BaseModel):
    name: str = Field(default="Palpandi P")
    email: str = Field(default="palulaptop@gmail.com")
    phone: str = Field(default="+91-8220925062")
    github: str = Field(default="github.com/PALPANDI-P")
    linkedin: str = Field(default="linkedin.com/in/palpandii")
    education: List[EducationEntry] = Field(default_factory=list)
    resume_variants: List[ResumeVariant] = Field(default_factory=list)
    target_titles: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    projects: List[CandidateProject] = Field(default_factory=list)
    preferred_company_types: List[str] = Field(default_factory=lambda: ["startup", "mid_size", "product"])
    location_weights: LocationWeights = Field(default_factory=LocationWeights)
    priority_cities: List[str] = Field(default_factory=lambda: ["Chennai", "Coimbatore", "Madurai", "Bangalore", "Mysore", "Kochi", "Trivandrum"])
    preferred_states: List[str] = Field(default_factory=lambda: ["Tamil Nadu", "Karnataka", "Kerala"])
    preferred_locations: List[str] = Field(default_factory=list)
    boost_keywords: List[str] = Field(default_factory=list)
    penalize_keywords: List[str] = Field(default_factory=list)
    experience_years: int = Field(default=0)
    summary: str = Field(default="")
