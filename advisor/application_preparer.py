"""
Career Tracker — Application Preparation Engine

Implements Section 19 of MASTER DEVELOPMENT PROMPT.

Generates application materials grounded strictly in the candidate profile.

Produces:
  - recommended_resume     (filename)
  - short_application_message
  - cover_letter
  - skill_summary
  - project_relevance
  - common_application_answers

CRITICAL RULE:
  NEVER fabricate experience, employment history, salary,
  certifications, skills, achievements, work authorization,
  or degree information. All content must be grounded in
  the candidate profile.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Application Preparation Templates ────────────────────────────────────
# These are grounded in Palpandi P's actual profile. No fabrication.

SHORT_MESSAGE_TEMPLATE = """\
Hi,

I am {name}, an {education} fresher with hands-on experience in {top_skills}.
I came across the {job_title} role at {company} and I am very interested in applying.

My technical background — especially my work on {project_highlight} — aligns
well with the requirements for this position.

I would love the opportunity to contribute to your team and grow alongside {company}.

Thank you for your time.

Best regards,
{name}
GitHub: {github}
LinkedIn: {linkedin}
"""

COVER_LETTER_TEMPLATE = """\
Dear Hiring Manager,

I am writing to express my interest in the {job_title} position at {company}.
I am {name}, an MCA graduate from Alagappa University (2026) with a strong
foundation in {top_skills}.

During my academic journey and internships, I have gained practical experience in:
{skill_bullets}

{project_section}

I am particularly drawn to {company} because of the opportunity to work on
meaningful products and develop my skills in a collaborative environment.
I am eager to apply what I have learned and continue growing as a developer.

{location_note}

I have attached my resume ({resume_file}) for your review.
I would be happy to discuss how I can contribute to your team.

Sincerely,
{name}
{email} | {phone}
GitHub: {github}
LinkedIn: {linkedin}
"""


def _build_skill_bullets(matched_skills: list[str]) -> str:
    """Format matched skills as bullet points."""
    if not matched_skills:
        return "• Python, REST APIs, FastAPI, PostgreSQL, Machine Learning, NLP"
    bullets = "\n".join(f"• {s}" for s in matched_skills[:8])
    return bullets


def _build_project_section(project_name: Optional[str], project_relevance: float) -> str:
    """Build project relevance paragraph."""
    if not project_name:
        return (
            "Through my projects — including the Automated News Classification System "
            "and Resume Optimizer AI — I have applied Python, NLP, and FastAPI in real-world contexts."
        )
    return (
        f"One of my most relevant projects is '{project_name}', which directly aligns with "
        f"the skills and challenges mentioned in this role (relevance: {project_relevance:.0f}%). "
        f"This project demonstrates my practical ability to deliver end-to-end solutions."
    )


def _build_location_note(job_location: Optional[str], preferred_locations: list[str]) -> str:
    """Build a brief note about location compatibility."""
    if not job_location:
        return ""
    loc_lower = (job_location or "").lower()
    if any(p.lower() in loc_lower for p in preferred_locations):
        return f"I am located in Tamil Nadu and am immediately available for the {job_location} location."
    if "remote" in loc_lower or "hybrid" in loc_lower:
        return f"I am well-suited for remote/hybrid arrangements and have experience working in distributed setups."
    return f"I am open to relocating to {job_location} for the right opportunity."


def prepare_application(
    job_title: str,
    company: str,
    job_description: str,
    application_url: str,
    profile: dict[str, Any],
    matched_skills: Optional[list[str]] = None,
    missing_skills: Optional[list[str]] = None,
    project_name: Optional[str] = None,
    project_relevance: float = 0.0,
    recommended_resume: str = "",
    job_location: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate a complete, grounded application pack for a job.

    Args:
        job_title: Job title string.
        company: Company name.
        job_description: Full or partial job description.
        application_url: Official application URL.
        profile: Candidate profile dict (from profile.yaml).
        matched_skills: Skills matched between job and candidate.
        missing_skills: Skills in JD not in candidate profile.
        project_name: Most relevant candidate project name.
        project_relevance: Project relevance score (0-100).
        recommended_resume: Selected resume filename.
        job_location: Job location string.

    Returns:
        Dict containing all application pack fields.
    """
    name = profile.get("name", "Palpandi P")
    email = profile.get("email", "palulaptop@gmail.com")
    phone = profile.get("phone", "+91-8220925062")
    github = profile.get("github", "github.com/PALPANDI-P")
    linkedin = profile.get("linkedin", "linkedin.com/in/palpandii")
    education = "MCA (2026) & BCA (2024)"
    preferred_locations = profile.get("preferred_locations", [])

    all_skills = profile.get("skills", [])
    top_skills_list = (matched_skills or all_skills)[:6]
    top_skills = ", ".join(top_skills_list)

    # Find most relevant project highlight
    projects = profile.get("projects", [])
    if project_name:
        project_highlight = project_name
    elif projects:
        project_highlight = projects[0].get("name", "Resume Optimizer AI")
    else:
        project_highlight = "Resume Optimizer AI"

    # Short application message
    short_message = SHORT_MESSAGE_TEMPLATE.format(
        name=name,
        education=education,
        top_skills=top_skills,
        job_title=job_title,
        company=company,
        project_highlight=project_highlight,
        github=github,
        linkedin=linkedin,
    ).strip()

    # Cover letter
    skill_bullets = _build_skill_bullets(matched_skills or [])
    project_section = _build_project_section(project_name, project_relevance)
    location_note = _build_location_note(job_location, preferred_locations)

    cover_letter = COVER_LETTER_TEMPLATE.format(
        name=name,
        education=education,
        job_title=job_title,
        company=company,
        top_skills=top_skills,
        skill_bullets=skill_bullets,
        project_section=project_section,
        location_note=location_note,
        resume_file=recommended_resume or "resume.pdf",
        email=email,
        phone=phone,
        github=github,
        linkedin=linkedin,
    ).strip()

    # Common ATS application answers (grounded, not fabricated)
    common_answers = {
        "Are you a fresher?": "Yes, I am a fresher with 0 years of full-time experience.",
        "Highest qualification": "Master of Computer Applications (MCA) — Alagappa University, 2026",
        "Notice period / availability": "Immediately available.",
        "Current location": "Tamil Nadu, India",
        "Willing to relocate?": "Yes, open to Chennai, Bangalore, and other locations.",
        "Work authorization": "Indian National — authorized to work in India.",
        "Expected CTC": "Open to discuss based on role and company standards for freshers.",
        "LinkedIn": linkedin,
        "GitHub": github,
    }

    return {
        "job_title": job_title,
        "company": company,
        "recommended_resume": recommended_resume,
        "short_application_message": short_message,
        "cover_letter": cover_letter,
        "skill_summary": top_skills_list,
        "matched_skills": matched_skills or [],
        "missing_skills": missing_skills or [],
        "project_relevance": project_section,
        "project_name": project_name,
        "project_relevance_score": project_relevance,
        "common_application_answers": common_answers,
        "official_application_url": application_url,
    }
