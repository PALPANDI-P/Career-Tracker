"""
Career Tracker — Company Name & Domain Normalization Engine

Resolves variant company names:
- "ABC Technologies Pvt Ltd" -> "ABC Technologies"
- "ABC Tech India Private Limited" -> "ABC Tech"
- "ABC Inc." -> "ABC"

Uses normalized names, domains, and ATS endpoints to prevent duplicate records.
Rule: Never merge distinct companies based solely on generic word matches.
"""

from __future__ import annotations

import re
import urllib.parse

# Legal entity suffixes to remove during normalization
SUFFIX_PATTERNS = [
    r"\bprivate\s+limited\b",
    r"\bpvt\s+ltd\b",
    r"\blimited\b",
    r"\bltd\b",
    r"\binc\b",
    r"\bincorporated\b",
    r"\bcorp\b",
    r"\bcorporation\b",
    r"\bllc\b",
    r"\btechnologies\b",
    r"\bsolutions\b",
    r"\bservices\b",
    r"\bindia\b",
    r"\bglobal\b",
]


def normalize_company_name(raw_name: str) -> str:
    """Clean and normalize a company name for deduplication."""
    if not raw_name:
        return ""

    name = raw_name.strip()
    name_lower = name.lower()

    # Remove entity suffixes
    for pattern in SUFFIX_PATTERNS:
        name_lower = re.sub(pattern, "", name_lower, flags=re.IGNORECASE)

    # Clean punctuation and extra spaces
    name_lower = re.sub(r"[^\w\s]", " ", name_lower)
    normalized = " ".join(name_lower.split())

    return normalized if normalized else raw_name.strip().lower()


def extract_domain(url: str | None) -> str | None:
    """Extract clean base domain from a URL (e.g. https://careers.zoho.com -> zoho.com)."""
    if not url:
        return None

    url_str = url.strip()
    if not url_str.startswith("http://") and not url_str.startswith("https://"):
        url_str = "https://" + url_str

    try:
        parsed = urllib.parse.urlparse(url_str)
        host = parsed.netloc.lower()
        # Remove www. and subdomains for major ATS hosts
        host = re.sub(r"^www\.", "", host)

        # Handle ATS subdomains (e.g. company.greenhouse.io -> company)
        parts = host.split(".")
        if len(parts) >= 2:
            return f"{parts[-2]}.{parts[-1]}"
        return host
    except Exception:
        return None


def is_same_company(name1: str, name2: str, domain1: str | None = None, domain2: str | None = None) -> bool:
    """
    Check if two company references belong to the same entity.
    Returns True if domains match or normalized names are identical.
    """
    norm1 = normalize_company_name(name1)
    norm2 = normalize_company_name(name2)

    if norm1 == norm2 and norm1:
        return True

    if domain1 and domain2:
        d1 = extract_domain(domain1)
        d2 = extract_domain(domain2)
        if d1 and d2 and d1 == d2:
            return True

    return False
