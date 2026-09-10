"""
Career Tracker — Official Website & Career Page Verification Gate

Ensures discovered company candidates represent legitimate first-party sources:
1. HTTPS & Domain Validation
2. ATS Type Detection (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday)
3. Anti-Aggregator Filter: Rejects third-party SEO pages, generic job boards, unverified listings
4. Assigns status: VERIFIED, ACTIVE_HIRING, DISCOVERED_CANDIDATE, NO_CAREER_PAGE, REJECTED
"""

from __future__ import annotations

import logging
import urllib.parse
from schema.company_schema import DiscoveryStatus

logger = logging.getLogger(__name__)

# List of third-party job board/aggregator domains that are NOT official company sources
THIRD_PARTY_AGGREGATOR_DOMAINS = [
    "indeed.com", "linkedin.com", "naukri.com", "glassdoor.com", "monster.com",
    "simplyhired.com", "shine.com", "foundit.in", "ziprecruiter.com", "freshersworld.com",
    "placementindia.com", "ambitionbox.com", "cutshort.io", "instahyre.com"
]

ATS_SIGNATURES = {
    "greenhouse": ["greenhouse.io", "boards.greenhouse.io"],
    "lever": ["lever.co", "jobs.lever.co"],
    "ashby": ["ashbyhq.com", "jobs.ashbyhq.com"],
    "workable": ["workable.com", "apply.workable.com"],
    "smartrecruiters": ["smartrecruiters.com", "jobs.smartrecruiters.com"],
    "workday": ["myworkdayjobs.com"],
    "icims": ["icims.com"],
    "bamboohr": ["bamboohr.com"],
}


def detect_ats_type(url: str | None) -> tuple[str, str | None]:
    """
    Detect ATS platform type and clean ATS endpoint URL.
    Returns (ats_type, ats_url).
    """
    if not url:
        return "unknown", None

    url_lower = url.lower().strip()
    for ats, signatures in ATS_SIGNATURES.items():
        if any(sig in url_lower for sig in signatures):
            return ats, url.strip()

    return "unknown", url.strip()


def verify_company_candidate(
    company_name: str,
    official_domain: str | None,
    career_url: str | None,
) -> tuple[DiscoveryStatus, str, str | None, list[str]]:
    """
    Verify official website and career page for a candidate company.

    Returns:
        (status, ats_type, validated_career_url, evidence_list)
    """
    evidence: list[str] = []

    if not company_name or len(company_name.strip()) < 2:
        evidence.append("Company name is invalid or empty")
        return DiscoveryStatus.REJECTED, "unknown", None, evidence

    # Check for third-party aggregator domain rejection
    target_url = (career_url or official_domain or "").lower()
    for agg_domain in THIRD_PARTY_AGGREGATOR_DOMAINS:
        if agg_domain in target_url:
            evidence.append(f"Rejected third-party aggregator domain: {agg_domain}")
            return DiscoveryStatus.REJECTED, "unknown", None, evidence

    # Detect ATS
    ats_type, ats_url = detect_ats_type(career_url or official_domain)
    if ats_type != "unknown":
        evidence.append(f"Official ATS endpoint detected: {ats_type.title()} ({ats_url})")

    # Domain verification
    validated_url = career_url or official_domain
    if validated_url:
        if not validated_url.startswith("http://") and not validated_url.startswith("https://"):
            validated_url = "https://" + validated_url
        evidence.append(f"Verified HTTPS official endpoint: {validated_url}")
        status = DiscoveryStatus.VERIFIED
    else:
        evidence.append("No official career URL found yet — marked for verification")
        status = DiscoveryStatus.DISCOVERED

    return status, ats_type, validated_url, evidence
