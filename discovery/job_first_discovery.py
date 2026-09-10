"""
Career Tracker — Job-First Company Discovery Engine

Reverses the discovery process:
When a relevant job (e.g. "Junior Python Developer") is found from a public job feed or API:
1. Identifies the posting company
2. Determines its official website & domain
3. Discovers its official career page / ATS endpoint
4. Inspects its COMPLETE job inventory (not just the single discovered job)
5. Adds the company to the monitoring registry
"""

from __future__ import annotations

import logging
from schema.job import Job
from schema.company_schema import DiscoveryCandidate
from discovery.normalization import extract_domain, normalize_company_name
from discovery.verification import detect_ats_type

logger = logging.getLogger(__name__)


def discover_company_from_job(job: Job) -> DiscoveryCandidate | None:
    """
    Reverse-map a discovered Job object to a DiscoveryCandidate company record.
    """
    if not job.company or len(job.company.strip()) < 2:
        return None

    company_name = job.company.strip()
    norm_name = normalize_company_name(company_name)

    # Attempt domain extraction from job URL or company string
    url_str = str(job.url) if job.url else None
    domain = extract_domain(url_str)
    ats_type, ats_url = detect_ats_type(url_str)

    career_url = ats_url or url_str

    candidate = DiscoveryCandidate(
        raw_name=company_name,
        domain=domain,
        career_url=career_url,
        source="job_first_discovery",
        snippet=f"Discovered via job: {job.title}",
        detected_location=job.location or job.city,
        tags=["job-first-discovery", job.job_category.value],
    )

    logger.info("Job-first discovery identified candidate company: %s (%s)", company_name, domain or "no domain")
    return candidate
